--
-- FS25 - Mixer Wagon Pellet Fix
--
-- Workaround für eine Design-Lücke im Straw Harvest Pack (Creative Mesh):
-- Stroh-/Heupellets sind ca. 4:1 komprimiert (aus ~4.000 l losem Stroh
-- entstehen ~1.000 l Pellets). Kippt man Pellets in einen Futtermischwagen,
-- zählt das Spiel aber nur die nackten Pellet-Liter 1:1 als Stroh bzw.
-- Heu - rund 75 % des Futterwerts verschwinden.
--
-- Dieses Skript wandelt Pellets beim Befüllen eines Mischwagens in die
-- ursprüngliche Menge um:
--
--     STRAW_PELLETS -> STRAW             (Faktor 4,0)
--     HAY_PELLETS   -> DRYGRASS_WINDROW  (Faktor 4,0)
--
-- Der Faktor ist bewusst FEST auf die Volumenkompression des Pelletierens
-- gesetzt (Liter rein / Liter raus, ~4:1) und wird NICHT aus dem
-- Masseverhältnis der Fülltypen abgeleitet: Das DLC gibt Pellets eine
-- realistische Dichte (massPerLiter 0,75 gegenüber Stroh 0,06 / Heu 0,07,
-- also Masseverhältnis 12,5 bzw. 10,7), das Pelletieren selbst ist im
-- Spiel aber nicht massenerhaltend. Eine Anrechnung nach Masse würde
-- deshalb Material aus dem Nichts erzeugen (getestet: 362 l Heupellets
-- wurden zu ~3.900 l Heu statt ~1.450 l). Neutral für das Gameplay ist
-- genau die Umkehrung der Volumenkompression.
--
-- Zusätzlich nehmen selbstfahrende Mischwagen Pellets vom Boden nur mit
-- halber Rate auf (PELLET_INTAKE_SPEED): durch den Faktor 4 füllt sich der
-- Mischwagen im Pellet-Haufen sonst viermal so schnell wie gewohnt. Was
-- nicht aufgenommen wird, bleibt liegen - es geht nichts verloren.
--
-- Es wird nur der Mischwagen angefasst; Verkauf, Einstreu und Lagerung
-- von Pellets bleiben unverändert. Die Umwandlung läuft durch dieselbe
-- Fill-Logik wie Vanilla (serverseitig), daher multiplayertauglich.
--
-- Alle Hooks sind pcall-gesichert: schlägt die Umwandlung fehl (z.B. nach
-- einem Spielupdate), wird der Mod dauerhaft deaktiviert, einmalig eine
-- Warnung geloggt und das Vanilla-Verhalten bleibt unberührt.
--

MixerWagonPelletFix = {}
MixerWagonPelletFix.modName = g_currentModName

-- Pellet-Fülltyp -> Ziel-Fülltyp. factor = Volumenkompression des
-- Pelletierens (Liter loses Material pro Liter Pellets), gemessen:
-- 1.209 l Heu -> 302 l Pellets, 1.029 l Stroh -> 258 l Pellets, je 4,0.
-- Weicht die Premos/Industriehalle davon ab, hier anpassen.
local CONVERSIONS = {
    { pellet = "STRAW_PELLETS", target = "STRAW",            factor = 4.0 },
    { pellet = "HAY_PELLETS",   target = "DRYGRASS_WINDROW", factor = 4.0 },
}

-- Dosierhilfe: Anteil der normalen Aufnahmerate, mit der ein selbstfahrender
-- Mischwagen Pellets vom Boden aufnimmt (1,0 = keine Drossel). Durch die
-- Umrechnung mit Faktor 4 füllt sich der Mischwagen in Pellet-Haufen sonst
-- viermal so schnell wie gewohnt; 0,5 halbiert das, 0,25 entspricht exakt
-- dem Tempo von losem Material.
--
-- Angesetzt wird an `shovelNode.fillLitersPerSecond`, also an der Rate, mit
-- der die Shovel-Spezialisierung Material vom Boden abräumt. Das ist der
-- einzig verlustfreie Weg: Was nicht abgeräumt wird, bleibt im Haufen
-- liegen.
--
-- Nicht über den Rückgabewert von addFillUnitFillLevel drosseln! Der wird
-- von Shovel:onUpdateTick ignoriert, das Material ist zu dem Zeitpunkt
-- bereits vom Boden entfernt und damit weg. Getestet: mit halber Annahme
-- ergaben 270 l Pellets 570 l statt 1.080 l Heu.
local PELLET_INTAKE_SPEED = 0.5

local conversions = nil -- fillTypeIndex -> { targetIndex = ..., factor = ... }
local mwpfFailed = false

local function fail(err)
    if not mwpfFailed then
        mwpfFailed = true
        Logging.warning("[%s] disabled after error: %s", MixerWagonPelletFix.modName, tostring(err))
    end
end

-- Fülltypen erst beim Kartenstart auflösen - beim Laden des Skripts sind
-- die DLC-Fülltypen im FillTypeManager noch nicht registriert
local function resolveConversions()
    conversions = {}
    for _, conf in ipairs(CONVERSIONS) do
        local pellet = g_fillTypeManager:getFillTypeByName(conf.pellet)
        local target = g_fillTypeManager:getFillTypeByName(conf.target)
        if pellet ~= nil and target ~= nil then
            conversions[pellet.index] = { targetIndex = target.index, factor = conf.factor }
            Logging.info("[%s] %s -> %s, Faktor %.2f",
                MixerWagonPelletFix.modName, conf.pellet, conf.target, conf.factor)
        end
    end
    if next(conversions) == nil then
        conversions = nil
        Logging.info("[%s] keine Pellet-Fülltypen gefunden (Straw Harvest Pack nicht aktiv?), Mod inaktiv",
            MixerWagonPelletFix.modName)
    end
end

function MixerWagonPelletFix:loadMap()
    if mwpfFailed then
        return
    end
    local ok, err = pcall(resolveConversions)
    if not ok then
        fail(err)
    end
end

function MixerWagonPelletFix:deleteMap()
    conversions = nil
end

-- Kern: Pellets beim Befüllen des Mischwagens in den Ursprungs-Fülltyp
-- umrechnen. Gibt nil zurück, wenn nichts umzuwandeln ist (dann läuft der
-- Vanilla-Pfad), sonst die verbrauchten Pellet-Liter, damit die Quelle
-- (Palette, Schaufel, Förderband) korrekt geleert wird.
--
-- Wichtig: MixerWagon.addFillUnitFillLevel ist selbst als overwritten
-- Spec-Funktion registriert - die Spezialisierungs-Chain reicht ihr als
-- erstes Argument den superFunc der FillUnit-Ebene durch. Unser Wrapper
-- sieht daher ZWEI superFuncs: superFunc (die originale MixerWagon-
-- Funktion, damit die Gruppen-Buchführung des Mischwagens mit dem schon
-- umgerechneten Fülltyp läuft) und fillUnitSuperFunc (FillUnit-Ebene,
-- wird unverändert an die originale Funktion weitergereicht).
local function convert(self, superFunc, fillUnitSuperFunc, farmId, fillUnitIndex, fillLevelDelta, fillTypeIndex, toolType, fillPositionData)
    if conversions == nil or fillLevelDelta == nil or fillLevelDelta <= 0 then
        return nil
    end
    local conv = conversions[fillTypeIndex]
    if conv == nil then
        return nil
    end
    -- nur intakte Mischwagen und nur deren Misch-Fülleinheit anfassen
    -- (Mischwagen haben i.d.R. genau eine)
    local spec = self.spec_mixerWagon
    if spec == nil then
        return nil
    end
    if spec.fillUnitIndex ~= nil and spec.fillUnitIndex ~= fillUnitIndex then
        return nil
    end
    local applied = superFunc(self, fillUnitSuperFunc, farmId, fillUnitIndex,
        fillLevelDelta * conv.factor, conv.targetIndex, toolType, fillPositionData)
    -- ab hier darf nichts mehr fehlschlagen (superFunc lief bereits - ein
    -- Fehler würde im Fallback des Hooks zu doppeltem Einfüllen führen)
    if type(applied) ~= "number" then
        return 0
    end
    return applied / conv.factor
end

-- Dosierhilfe: Aufnahmerate des Shovel-Knotens senken, solange Pellets vom
-- Boden aufgenommen werden. getShovelNodeIsActive wird in
-- Shovel:onUpdateTick ausgewertet, bevor das Material vom Boden geholt wird
-- (freeCapacity = min(freeCapacity, shovelNode.fillLitersPerSecond * dt)) -
-- eine niedrigere Rate lässt den Rest also im Haufen liegen.
--
-- Betrifft nur selbstfahrende Mischwagen mit Shovel-Knoten (Faresin PF226,
-- Kuhn SPW Intense); gezogene Mischwagen können ohnehin nicht vom Boden
-- aufnehmen. Fremde Fahrzeuge (Radlader, Bagger) bleiben unberührt, weil
-- auf spec_mixerWagon geprüft wird.
local function throttleShovelNode(self, superFunc, shovelNode)
    local isActive = superFunc(self, shovelNode)
    if PELLET_INTAKE_SPEED >= 1.0 or conversions == nil or shovelNode == nil then
        return isActive
    end
    if self.spec_mixerWagon == nil then
        return isActive
    end

    -- Ausgangsrate merken; ändert sie jemand anderes (Konfiguration, anderer
    -- Mod), wird der neue Wert zur Basis
    local rate = shovelNode.fillLitersPerSecond
    if shovelNode.mwpfLastSet == nil or rate ~= shovelNode.mwpfLastSet then
        shovelNode.mwpfBaseRate = rate
    end
    local base = shovelNode.mwpfBaseRate
    if base == nil or base <= 0 or base == math.huge then
        return isActive -- ohne konfigurierte Rate gibt es nichts zu skalieren
    end

    -- Fülltyp des laufenden Aufnahmevorgangs (Shovel setzt ihn am Ende von
    -- onUpdateTick); im ersten Tick eines Haufens greift die Drossel daher
    -- noch nicht - unkritisch, es geht nichts verloren
    local spec = self.spec_shovel
    local loadingFillType = spec ~= nil and spec.loadingFillType or nil

    if isActive and loadingFillType ~= nil and conversions[loadingFillType] ~= nil then
        shovelNode.fillLitersPerSecond = base * PELLET_INTAKE_SPEED
    else
        shovelNode.fillLitersPerSecond = base
    end
    shovelNode.mwpfLastSet = shovelNode.fillLitersPerSecond

    return isActive
end

function MixerWagonPelletFix.installHooks()
    if MixerWagon == nil or MixerWagon.addFillUnitFillLevel == nil then
        Logging.warning("[%s] MixerWagon.addFillUnitFillLevel not found, mod inactive", MixerWagonPelletFix.modName)
        return
    end

    if Shovel ~= nil and Shovel.getShovelNodeIsActive ~= nil then
        Shovel.getShovelNodeIsActive = Utils.overwrittenFunction(Shovel.getShovelNodeIsActive,
            function(self, superFunc, shovelNode)
                if mwpfFailed then
                    return superFunc(self, shovelNode)
                end
                local ok, result = pcall(throttleShovelNode, self, superFunc, shovelNode)
                if ok then
                    return result
                end
                fail(result)
                return superFunc(self, shovelNode)
            end)
    else
        Logging.info("[%s] Shovel.getShovelNodeIsActive nicht gefunden, Dosierhilfe inaktiv",
            MixerWagonPelletFix.modName)
    end

    MixerWagon.addFillUnitFillLevel = Utils.overwrittenFunction(MixerWagon.addFillUnitFillLevel,
        function(self, superFunc, ...)
            if not mwpfFailed then
                -- convert ruft superFunc höchstens einmal auf und rechnet danach
                -- nur noch mit vorab geprüften Zahlen - schlägt es vor dem Aufruf
                -- fehl, ist noch nichts eingefüllt und der Vanilla-Pfad unten
                -- bleibt korrekt
                local ok, result = pcall(convert, self, superFunc, ...)
                if ok then
                    if result ~= nil then
                        return result
                    end
                else
                    fail(result)
                end
            end
            return superFunc(self, ...)
        end)
end

MixerWagonPelletFix.installHooks()
addModEventListener(MixerWagonPelletFix)
