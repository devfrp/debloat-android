#!/usr/bin/env python3
"""Base de données de bloatware connus, par catégorie de risque.

Format :
  BLOAT_DB[pkg]      = (risk, nom_affiché, note)   risk = safe | advanced
  FORBIDDEN[pkg]     = (nom_affiché, note)         composants protégés (jamais désinstallables via cette app)

Recherche par préfixe gérée par FORBIDDEN_PREFIXES (ex. tout `com.android.*`).

⚠️ La base s'appuie sur l'état de l'art public (guides de débloat communautaires).
Elle n'est PAS exhaustive : un paquet absent de cette base apparaît comme « inconnu »
dans l'interface, à évaluer par l'utilisateur.
"""
from __future__ import annotations

RISK_SAFE = "safe"            # removable without real risk
RISK_ADVANCED = "advanced"    # heavier confirmation
RISK_FORBIDDEN = "forbidden"  # protected, uninstall blocked by the app
RISK_UNKNOWN = "unknown"      # not in the database -> end user decides

S, A, F = RISK_SAFE, RISK_ADVANCED, RISK_FORBIDDEN  # writing aliases

FORBIDDEN_PREFIXES: tuple[str, ...] = (
    "com.android.",                          # Android core (systemui, providers, chrome, launcher3…)
    "android.",                              # AOSP packages without prefix
    "com.google.android.trichromelibrary",   # Mainline modules (WebView engine)
)

FORBIDDEN: dict[str, tuple[str, str]] = {
    # ------------------------------------------------------------------ Google
    "com.google.android.gms": ("Google Play services", "Absolument central : la plupart des apps et des fonctions du système dépendent de GMS."),
    "com.google.android.gsf": ("Google Services Framework", "Cœur du système Google."),
    "com.google.android.gsf.login": ("Connexion Google (GSF)", "Cœur du système Google."),
    "com.google.android.webview": ("Android WebView", "Sans WebView, une foule d'applications plantent."),
    "com.google.android.configupdater": ("Mise à jour de configuration", "Certificats de sécurité et ajustements système."),
    "com.google.android.ext.services": ("Android Services Library", "Services système critiques."),
    "com.google.android.ext.shared": ("Services système partagés", "Services système critiques."),
    "com.google.android.modulemetadata": ("Module metadata", "Modules Play System / Mainline."),
    "com.google.android.inputmethod.latin": ("Gboard (clavier)", "Sans clavier tiers, plus rien à écrire."),
    # ------------------------------------------------------------------ Samsung
    "com.sec.android.app.launcher": ("One UI Home (lanceur Samsung)", "Retirer le lanceur = écran d'accueil mort."),
    "com.samsung.android.honeyboard": ("Clavier Samsung", "Clavier système."),
    "com.samsung.android.dialer": ("Samsung Téléphone", "App d'appels."),
    "com.samsung.android.contacts": ("Samsung Contacts", "Carnet d'adresses."),
    "com.samsung.android.sm.core": ("Soin de l'appareil (core)", "Gestion batterie / optimisation."),
    # ------------------------------------------------------------------ Xiaomi
    "com.miui.home": ("Lanceur MIUI", "Écran d'accueil."),
    "com.miui.securitycenter": ("Sécurité et batterie (MIUI)", "Gestion permissions/batterie du système."),
    "com.miui.securityadd": ("Composant sécurité MIUI", "Dépendance du centre de sécurité."),
    # ------------------------------------------------------------------ Huawei
    "com.huawei.systemmanager": ("Gestionnaire système (Huawei)", "Permissions / démarrage applications."),
    # ------------------------------------------------------------------ Sony
    "com.sonymobile.home": ("Xperia Home (lanceur)", "Écran d'accueil."),
}

BLOAT_DB: dict[str, tuple[str, str, str]] = {
    # ======================================================== Facebook / Meta
    "com.facebook.appmanager": (S, "Facebook App Manager", "Installe/met à jour l'app Facebook en arrière-plan."),
    "com.facebook.services": (S, "Facebook Services", "Services Facebook en arrière-plan."),
    "com.facebook.system": (S, "Facebook App Installer", "Pré-installateur de l'app Facebook."),
    # ================================================================ Netflix
    "com.netflix.partner.activation": (S, "Netflix (activation partenaire)", "Stub d'activation Netflix."),
    "com.netflix.mediaclient": (A, "Netflix", "Application Netflix."),
    # ================================================================= Google
    "com.google.android.feedback": (S, "Retours Google", "Signalement des bugs / télémétrie."),
    "com.google.android.partnersetup": (S, "Partner Setup", "Pré-configuration Google du constructeur."),
    "com.google.android.printservice.recommendation": (S, "Recommandations d'imprimantes", "Suggestions d'impression."),
    "com.google.android.tts": (A, "Synthèse vocale Google", "Nécessaire aux lecteurs d'écran (TalkBack) et à la dictée."),
    "com.google.android.marvin.talkback": (A, "TalkBack", "Lecteur d'écran : désactiver seulement si vous n'utilisez pas l'accessibilité."),
    "com.google.android.apps.tachyon": (A, "Google Meet (ex-Duo)", "App d'appels vidéo."),
    "com.google.android.videos": (A, "Google TV", "App de lecture de films/séries achetés."),
    "com.google.android.apps.youtube.music": (A, "YouTube Music", "App de musique."),
    "com.google.android.gm": (A, "Gmail", "À retirer seulement si vous utilisez un autre client mail."),
    "com.google.android.googlequicksearchbox": (A, "Barre de recherche Google", "Widget du bureau ; le retrait peut casser l'assistant."),
    # ============================================================= Microsoft
    "com.microsoft.appmanager": (A, "Link to Windows", "Connexion téléphone ↔ PC."),
    "com.microsoft.skydrive": (A, "OneDrive", "Cloud Microsoft."),
    "com.microsoft.office.officehubrow": (A, "Microsoft 365 (Office)", "Suite bureautique préinstallée."),
    "com.microsoft.office.outlook": (A, "Outlook", "Client mail Microsoft."),
    # =============================================== Autres apps tierces préinstallées
    "com.linkedin.android": (A, "LinkedIn", "Souvent préinstallé (Samsung…) comme app système."),
    "com.spotify.music": (A, "Spotify", "Si préinstallé dans l'image système."),
    "com.amazon.mShop.android.shopping": (A, "Amazon Shopping", "App de la boutique Amazon."),
    "com.orange.aura.oabo": (A, "Orange Aura", "Sauvegarde opérateur Orange."),
    # =============================================================== Samsung
    "com.samsung.android.app.spage": (S, "Samsung Free / Daily", "Rangée de contenus sur l'écran d'accueil."),
    "com.samsung.android.game.gametools": (S, "Game Tools", "Outils pendant les jeux."),
    "com.samsung.android.game.gamehome": (S, "Game Launcher", "Bibliothèque de jeux."),
    "com.samsung.android.game.gos": (A, "Game Optimizing Service", "Peut brider les FPS ; le retirer se fait au détriment des profils Samsung."),
    "com.samsung.android.arzone": (S, "AR Zone", "Fonctions caméra en réalité augmentée."),
    "com.samsung.android.aremoji": (S, "AR Emoji", "Avatars animés."),
    "com.sec.android.mimage.avatar.sticker": (S, "Stickers avatar", "Stickers AR."),
    "com.samsung.android.spay": (A, "Samsung Pay", "Paiement NFC Samsung."),
    "com.samsung.android.spayfw": (A, "Framework Samsung Pay", "Dépendance de Samsung Pay."),
    "com.samsung.android.bixby.agent": (A, "Bixby", "Assistant vocal Samsung."),
    "com.samsung.android.bixby.wakeup": (A, "Bixby (réveil)", "Sons de mot déclencheur."),
    "com.samsung.android.visionintelligence": (A, "Bixby Vision", "Vision (reconnaissance) Bixby."),
    "com.samsung.android.mdecservice": (A, "Appels/SMS relayés", "Comms entre appareils Samsung."),
    "com.samsung.android.dqagent": (S, "Device Quality Agent", "Collecte de diagnostics qualité."),
    "com.sec.android.diagmonagent": (S, "DiagMon Agent", "Diagnostics / télémétrie Samsung."),
    "com.sec.android.soagent": (S, "Agent de mise à jour", "Analyse de compatibilité des mises à jour."),
    "com.sec.android.app.hwmoduletest": (S, "Tests matériels", "Menu d'ingénierie caché."),
    "com.sec.android.app.billing": (A, "Samsung Checkout", "Paiement in-app Samsung."),
    "com.samsung.android.themestore": (A, "Galaxy Themes", "Boutique de thèmes/icônes."),
    "com.samsung.android.scloud": (A, "Samsung Cloud", "Sauvegarde cloud Samsung."),
    "com.samsung.android.sm.devicesecurity": (A, "Sécurité de l'appareil (McAfee)", "Analyseur antivirus ; doublon avec Play Protect."),
    "com.samsung.android.oneconnect": (A, "SmartThings", "Hub d'appareils connectés."),
    "com.samsung.android.rubin.app": (A, "Service de personnalisation", "Recommandations / télémétrie."),
    "com.samsung.android.knox.analytics.uploader": (S, "Knox Analytics", "Télémétrie Knox."),
    "com.samsung.android.beaconmanager": (S, "Gestion des balises", "Scan de balises Bluetooth (détection d'appareils proches)."),
    "com.samsung.android.app.watchmanager": (A, "Galaxy Wearable", "À garder si vous avez une montre/buds."),
    "com.samsung.android.da.daagent": (A, "Dual Messenger", "Duplication d'apps (2 comptes)."),
    "com.samsung.android.mobileservice": (A, "Samsung Experience Service", "Partage/sync via le compte Samsung."),
    "com.samsung.android.mdx": (A, "Link to Windows (service)", "Service côté Samsung du lien PC."),
    "com.samsung.android.app.tips": (S, "Astuces", "Panneau de conseils/tutoriels."),
    "com.samsung.android.dynamiclock": (S, "Écran de verrouillage dynamique", "Fonds d'écran rotatifs."),
    "com.sec.android.app.popupcalculator": (S, "Calculatrice Samsung", "Si vous utilisez une autre calculatrice."),
    "com.sec.android.app.sbrowser": (A, "Samsung Internet", "Remplacez le navigateur avant de retirer."),
    "com.samsung.android.email.provider": (A, "E-mail Samsung", "Client mail Samsung."),
    "com.samsung.android.calendar": (A, "Agenda Samsung", "Si vous dépendez du calendrier Samsung, gardez-le."),
    "com.samsung.android.app.notes": (A, "Samsung Notes", "À garder si vous l'utilisez (S Pen)."),
    "com.samsung.android.messaging": (A, "Messages Samsung", "Souvent app SMS PAR DÉFAUT : remplacez-la avant."),
    "com.sec.android.daemonapp": (A, "Framework météo Samsung", "Widget météo ; certains widgets dépendent de lui."),
    "com.sec.spp.push": (A, "Samsung Push Service", "Notifications des apps Samsung."),
    "com.sec.android.app.clockpackage": (A, "Horloge & alarmes", "⚠️ Contient l'alarme système Samsung."),
    "com.samsung.android.app.cocktailbarservice": (A, "Edge Panels", "Panneaux latéraux."),
    "com.samsung.android.app.dressroom": (A, "Fonds & thèmes", "Édition de thèmes/fonds."),
    "com.samsung.android.stickercenter": (S, "Centre de stickers", "Gestion des stickers."),
    "com.sec.android.easyMover.Agent": (S, "Smart Switch (agent)", "Assistant de transfert vers un nouveau téléphone."),
    "com.samsung.android.smartswitchassistant": (S, "Smart Switch Assistant", "Assistant de transfert."),
    # ================================================================ Xiaomi
    "com.miui.yellowpage": (S, "Pages jaunes", "Annuaire local."),
    "com.miui.msa.global": (S, "Publicités système MIUI", "Injections de pub des écrans système."),
    "com.miui.analytics": (S, "Analytics", "Télémétrie Xiaomi."),
    "com.miui.bugreport": (S, "Rapport de bug", "Retours utilisateurs."),
    "com.miui.cleaner": (S, "Nettoyeur", "Optimisation stockage avec pubs."),
    "com.miui.hybrid": (S, "Quick Apps", "Pseudo-store d'app « instantanées », intrusive."),
    "com.miui.hybrid.accessory": (S, "Quick Apps (accessoire)", "Dépendance Quick Apps."),
    "com.miui.miservice": (S, "Services & feedback", "SAV Xiaomi."),
    "com.miui.touchassistant": (S, "Quick Ball", "Bulle d'assistance tactile."),
    "com.miui.huanji": (A, "Mi Mover", "Outil de migration (utile 1 fois)."),
    "com.miui.cloudservice": (A, "Mi Cloud", "Sauvegarde cloud Xiaomi."),
    "com.miui.cloudbackup": (A, "Sauvegarde Mi Cloud", "Sauvegarde cloud Xiaomi."),
    "com.miui.player": (A, "Mi Musique", "App musique Xiaomi."),
    "com.miui.videoplayer": (A, "Mi Vidéo", "App vidéo Xiaomi."),
    "com.miui.gallery": (A, "Galerie (MIUI)", "⚠️ Si vous l'utilisez comme app photos."),
    "com.miui.weather2": (A, "Météo (MIUI)", "App météo/widget."),
    "com.miui.fm": (A, "Radio FM", "À garder si vous écoutez la radio."),
    "com.xiaomi.mipicks": (A, "GetApps", "Boutique d'applications Xiaomi."),
    "com.xiaomi.midrop": (A, "ShareMe", "Transfert de fichiers en Wi-Fi direct."),
    "com.xiaomi.jr": (A, "Mi Finance", "Services financiers Xiaomi."),
    "com.xiaomi.payment": (A, "Xiaomi Pay", "Paiement Xiaomi."),
    "com.micredit.in": (A, "Mi Crédit", "Microcrédit Xiaomi (Inde)."),
    "com.xiaomi.mi_connect_service": (A, "Mi Connect", "Interconnexion d'appareils Xiaomi."),
    # ================================================== OPPO / Realme / OnePlus
    "com.heytap.market": (A, "App Market (Heytap)", "Boutique Oppo/OnePlus/Realme."),
    "com.coloros.childrenspace": (S, "Espace enfants", "Mode enfant."),
    "com.coloros.gamespace": (A, "Game Space", "Hub de jeux ColorOS."),
    "com.coloros.oppomarket": (A, "Boutique Oppo (ancienne)", "Boutique ColorOS."),
    "com.coloros.video": (A, "Vidéo (Oppo)", "App vidéo ColorOS."),
    "com.oppo.music": (A, "Musique (Oppo)", "App musique ColorOS."),
    "com.nearme.statistics.rom": (S, "Statistiques (ColorOS)", "Télémétrie du système."),
    "com.coloros.weather2": (A, "Météo (ColorOS)", "App météo."),
    "com.coloros.speechassist": (A, "Assistant vocal (ColorOS)", "Assistant Oppo."),
    "com.heytap.openid": (A, "Service OpenID (Heytap)", "Identifiant publicitaire/compte Heytap."),
    # ============================================================ Huawei/Honor
    "com.huawei.appmarket": (A, "AppGallery", "Boutique Huawei."),
    "com.huawei.android.totemweather": (A, "Météo (Huawei)", "App/widget météo."),
    "com.huawei.himovie": (A, "Huawei Vidéo", "App vidéo Huawei."),
    "com.huawei.music": (A, "Musique Huawei", "App musique Huawei."),
    "com.huawei.gamebox": (A, "Huawei Game Center", "Hub de jeux."),
    "com.huawei.vassistant": (A, "Assistant vocal Huawei", "Assistant vocal."),
    "com.huawei.browser": (A, "Navigateur Huawei", "Remplacez avant de retirer."),
    "com.huawei.phoneservice": (A, "Mon Huawei (SAV)", "App d'assistance après-vente."),
    "com.huawei.parentcontrol": (A, "Contrôle parental", "À garder s'il y a des enfants."),
    # =========================================================== Sony / LG / Transsion
    "com.sonymobile.xperiaweather": (A, "Météo Xperia", "App/widget météo Sony."),
    "com.sonymobile.support": (A, "Support Xperia", "App d'assistance Sony."),
    "com.lge.sizechangable.weather": (A, "Météo LG", "App/widget météo LG."),
    "com.transsion.palmpay": (A, "PalmPay", "Portefeuille Tecno/Infinix."),
    "com.transsion.palmstore": (A, "Palm Store", "Boutique Tecno/Infinix."),
    "com.transsion.childmode": (S, "Mode enfant", "Mode enfant Tecno/Infinix."),
}


def lookup(package: str) -> tuple[str, str, str]:
    """Renvoie (risque, nom lisible, note) pour un nom de paquet."""
    if package in FORBIDDEN:
        name, note = FORBIDDEN[package]
        return RISK_FORBIDDEN, name, note
    for prefix in FORBIDDEN_PREFIXES:
        if package.startswith(prefix):
            return (
                RISK_FORBIDDEN,
                "Composant Android",
                "Package central d'Android (préfixe protégé, non désinstallable via cette app).",
            )
    entry = BLOAT_DB.get(package)
    if entry:
        risk, name, note = entry
        return risk, name, note
    return RISK_UNKNOWN, "", ""
