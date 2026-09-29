#!/usr/bin/env python3
"""Assign game classes (global ns + inferno::) to functional modules by name rules; sum code size.
Writes modules_map.txt: module -> classes (size)."""
import collections, re, os
BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
seen = {}
for line in open(os.path.join(BASE, 'symbols_all_grouped.tsv')):
    if line.startswith('addr\t'): continue
    a, sz, t, grp, scope, member, dem = line.rstrip('\n').split('\t')
    if grp.startswith('C:'): continue
    key = a
    if key in seen: continue
    seen[key] = (int(sz, 16) if sz else 0, t, grp, scope, member, dem)
RULES = [
 ('battle: script VM (behaviors DSL: operators/conditions)', r'^(inferno::)?(Script(Operator|Condition)\w*|I?Script\w*|\w+Operator|\w+Condition[A-Z]*|DistanceToTarget\w*|HealthCondition\w*|TargetHealthCondition\w*|ItemCondition\w*|VariableCondition\w*|OnCooldownCondition|HasAbility|CanShootTarget|ApplyShield|ComponentScriptExecutor|ComponentVariables|ComponentCooldowns)$'),
 ('battle: client real-time sim (CRj*)', r'^(CRjGame|CRjUnit(::\w+)?|CRjMapObject|CRjTurret|CRjBuilding|CRjPlayer|CRjTarget|CRjGlobalAbility(::\w+)?|CRjBatleScheduler(::\w+)?|CRjMapEffect|RjMapEffect\w+|RjEffect|RjEffectController|RjTracer|CRjAreaEffectBuilder|BaseMapObject|RjEntityStats|StatsData|RjExpendable|RjAbilityPanelController|MercenaryAbilsData|IWaypointOperatorData|\w+WaypointOperatorData|RjBattleSaver(::\w+)?)$'),
 ('battle: scene/map/render (BattleScene, IsometricMap, anim)', r'^(BattleScene(::\w+)?|IsometricMap|LogicMap|LogicMapObject|CRjAnimationController|RjAnimation\w+|CRjObjectBuilder|RjMapObjectVisualInfo|RjCameraHelper|RjHighlightHelper|CRjProgressBar|RjShaderEffectAction|RjRenderTexture|CCVignetteLayer|CCMaskSprite|CCLayerPanZoom|RjGeometry.*)$'),
 ('battle: server-side simulator (inferno::Simulator/Entity*)', r'^inferno::(Simulator|Field|Entity\w*(::\w+)?|Component\w+|Battle|BattleRoom(::\w+)?|BattleInfo|Pvp(::\w+)?|Mission(StartParams|FinishParams)?(::\w+)?)$'),
 ('data libraries (config.xml -> *Data)', r'^(\w+Library|AbstractLibrary|\w+Data(::\w+)?|LocaleScopeType|iLibrary)$'),
 ('economy/colony state (City, *System, GameSystem)', r'^(City|CityScene(::\w+)?|\w+System(::\w+)?|GameSystem|SystemElement|LocalWorldModel|IWorldModel|Building\w*|Contract\w*|Resource|Item|ItemSystemCount|Timing|Ticker|Territory\w*|Unit(Class|Equipment\w*|Stat\w*|LevelChangedInfo)?|Expendable|Explorer|Invasion|Perk|Tax|Offer|Pack\w*|Catalog\w*|CruisingGun\w*|Indicator|Notification|Citizen\w*|RjCitizen|RjCityRoads|RjCityUtils|RjBuildingArrowsHelper|Campaign|Chapter|StarSystem|SpaceportStoreItem\w*|Requirement|Broadcaster|SelfBroadcaster|ParamsContainer|IParamsContainer|WalkAndChatData|DismissAction|DismissProcess|RandomCueAction|KickAwayData|CitizenAction|StealMessageData|ExecutionProcess|hasCost|PriceData|Random)$'),
 ('quests/requirements/achievements (client)', r'^(Quest\w*|Condition\w+|Provider\w+|Task\w+|IRequirementChecker|\w+Checker|IQuestRewardData|\w+RewardData|IProvider|ICondition|IRestriction|Rj(And|Or|Simple)Restriction|RjAchieve\w*|RjAchievement\w*|AchieveSystem|SubmitQuestAction|RjQuestLocker|RewardRenderHelper|RewardRenderInfo|TaskRenderHelper)$'),
 ('tutorial', r'^(Tutorial\w*)$'),
 ('net protocol client (RjCommander/Proxy/Parsers/Handlers)', r'^(RjCommander|RjCommandProxy(::\w+)?|RjCommandParser|RjProxy|RjParseHandler|RjConnection\w*|\w+Parser|\w+Handler|\w+Hanler|\w+Info|INotificationInfo|InitGameData|UnknownUserData|EchoData|LogInfo|RoomInfo|EnemyInfo|LastWinnerInfo|RjOfflineChecker\w*|RjOfflinePopup)$'),
 ('logic core ("server" compiled in: inferno::User/CRequestHandler/config)', r'^(inferno::(User(::\w+)?|CRequestHandler|LocalGameContext|IGameContext|IEnvironment|IHttpRequestHandler|UserEvent\w*(::\w+)?|configuration(::\w+)*|ICity\w*|City\w+|Give\w+|Take\w+|Set\w+|Move\w+|Start\w+|Stop\w+|Modify\w+|Apply\w+|Remove\w+|Jackpot\w*|SlotMachine(::\w+)?|LogAction|SendNotification|\w+E|\w+G|\w+GE|\w+L|\w+LE|Is\w+|LogicError(::\w+)?|MissionError(::\w+)?|UnknownUserError|Timer(::\w+)?|Notification|Building(::\w+)?|jackpot(::\w+)*|ErrorCodeMessage|Mission)|skzk(::\w+)*)$'),
 ('saves/cloud (RjSaveManager, GPGS snapshots)', r'^(RjSave\w*|RjSaved\w*|RjSnapshot|GPGSManager|RjLoadGameDialog(::\w+)?|RJCrypt|CSHA1|CHMAC_SHA1|TZip|TTreeState|RjEmailHelper|PEMStripper|ValidateHelper)$'),
 ('social (FB/Twitter/GPGS/achievements)', r'^(RjSocialManager\w*|Ezi\w+|FB\w+|RjFbLikeHelper|RjTwitter\w*|Twitte\w+|TwitterDialogHelper|oAuth|twitCurl|RjFriendsDialog\w*(::\w+)?|RjQuestSharingDialog|RjSocialQuests\w+)$'),
 ('payments (avalon IAP, RjInAppManager, offers UI)', r'^(RjInAppManager(::\w+)?|avalon(::\w+)*|RjBuyCreditsDialog|RjOfferDialog|RjBuyConfirmDialog|RjBuySomethingPopup\w*)$'),
 ('analytics/push/downloads/events', r'^(RjAnalyticsManager|RjGAHandler|IRjAnalyticHandler|GAEvent|AnalyticMethod|AnalyticType|RjPushManager|RjFileDownloader|RjPackage\w+(::\w+)?|RjEventsManager(::\w+)?|RjVersionManager|RjSystem\w+|sysinfo|RjMonkeyTouchLogger|RjFixes|AppConfig|RjAppCtrlHelper)$'),
 ('UI framework (CRjInterface, dialogs, custom CCB nodes)', r'^(CRjInterface|CRjDialog\w*|Rj\w*Dialog\w*(::\w+)?|Rj\w*Popup\w*|Rj\w*Widget|Rj\w*Node|RjRewardsTemplate|RjCoverFlowView|CRjScrollListView\w*(::\w+)?|CC\w+Loader|CCCheckBox|CCFocusLayer|CCLabelTTFSize|CCNodeSelector|CCPointsProgressTimer|CCTableNode|CCTextButton|CCTextLayout|CancelTouchLayer|CRjGestureRecognizer\w*|RjMessageBox|RjTutorialMapMove|RjArrowWidget|RjPreloader\w*|RjWakeUpScene|ChaptersScene|RjWorldGotoDialogBase|NotificationRenderHelper|RjArmyWeaponNode|RjCampaignsNode|RjEventNode)$'),
 ('app/sound/resources', r'^(AppDelegate|CRjSoundSystem(::\w+)?|FSoundManager|SoundKind|RjResourceManager|RjUtils|RjDirectionEnum|RjNewEntityHelperNs(::\w+)?|CRjDebugRect|CRjLogicDelegate)$'),
]
RX = [(n, re.compile(r)) for n, r in RULES]
LIBTOP = {'CryptoPP','std','__gnu_cxx','cocos2d','CocosDenshion','gpg','pugi','tinyxml2','rapidxml','CSJson','cs','google','(global-func)','_JNIEnv','const*'}
mod_size = collections.Counter(); mod_classes = collections.defaultdict(collections.Counter); unassigned = collections.Counter()
for a, (sz, t, grp, scope, member, dem) in seen.items():
    top = re.sub(r'<.*', '', grp)
    if top in LIBTOP or scope.startswith('b2') or scope == '(free)': continue
    cls = re.sub(r'<.*', '', scope)
    for n, rx in RX:
        if rx.match(cls):
            mod_size[n] += sz if t in ('T', 'W') else 0
            mod_classes[n][cls] += sz if t in ('T', 'W') else 0
            break
    else:
        unassigned[cls] += sz if t in ('T', 'W') else 0
with open(os.path.join(BASE, 'modules_map.txt'), 'w') as f:
    f.write('# Game-specific classes grouped into modules by naming rules (heuristic). Size = sum of sized T/W symbols (bytes of Thumb code).\n')
    for n, s in mod_size.most_common():
        f.write(f'\n## {n}: {s} bytes, {len(mod_classes[n])} classes\n')
        f.write('   ' + ', '.join(f'{c}({v})' for c, v in mod_classes[n].most_common()) + '\n')
    f.write(f'\n## UNASSIGNED ({sum(unassigned.values())} bytes)\n   ' + ', '.join(f'{c}({v})' for c, v in unassigned.most_common()) + '\n')
for n, s in mod_size.most_common(): print(f'{s:8d}  {len(mod_classes[n]):4d} cls  {n}')
print('unassigned:', sum(unassigned.values()), unassigned.most_common(40))
