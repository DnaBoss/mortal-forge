// Stable macOS-style layout for Plasma 6.
// Uses only built-in Plasma widgets and the already installed WhiteSur assets.

const existingPanels = panels();
for (let index = 0; index < existingPanels.length; index += 1) {
    existingPanels[index].remove();
}

const topPanel = new Panel();
topPanel.screen = 0;
topPanel.location = "top";
topPanel.height = 32;
topPanel.lengthMode = "fill";
topPanel.hiding = "none";
topPanel.floating = 0;

const launcher = topPanel.addWidget("org.kde.plasma.kickoff");
launcher.currentConfigGroup = ["Shortcuts"];
launcher.writeConfig("global", "Alt+F1");

topPanel.addWidget("org.kde.plasma.appmenu");
topPanel.addWidget("org.kde.plasma.panelspacer");

const tray = topPanel.addWidget("org.kde.plasma.systemtray");
tray.currentConfigGroup = ["General"];
tray.writeConfig("extraItems", [
    "org.kde.plasma.networkmanagement",
    "org.kde.plasma.volume",
    "org.kde.plasma.bluetooth",
    "org.kde.plasma.battery",
    "org.kde.plasma.brightness",
    "org.kde.plasma.notifications",
    "org.kde.plasma.clipboard",
    "org.kde.plasma.manage-inputmethod",
    "org.kde.plasma.devicenotifier"
]);

const clock = topPanel.addWidget("org.kde.plasma.digitalclock");
clock.currentConfigGroup = ["Appearance"];
clock.writeConfig("showSeconds", false);
clock.writeConfig("fontWeight", 400);
clock.writeConfig("showDate", false);

const dock = new Panel();
dock.screen = 0;
dock.location = "bottom";
dock.height = 66;
dock.lengthMode = "fit";
dock.alignment = "center";
dock.hiding = "dodgewindows";
dock.floating = 1;

const tasks = dock.addWidget("org.kde.plasma.icontasks");
tasks.currentConfigGroup = ["General"];
tasks.writeConfig("launchers", [
    "preferred://filemanager",
    "preferred://browser",
    "applications:org.kde.konsole.desktop",
    "applications:systemsettings.desktop"
]);
tasks.writeConfig("showOnlyCurrentDesktop", false);
tasks.writeConfig("showOnlyCurrentScreen", true);
dock.addWidget("org.kde.plasma.trash");

const desktop = desktopForScreen(0);
desktop.wallpaperPlugin = "org.kde.image";
desktop.currentConfigGroup = ["Wallpaper", "org.kde.image", "General"];
desktop.writeConfig("DynamicMode", 0);
desktop.writeConfig("Image", "file:///home/cash/.local/share/wallpapers/WhiteSur-dark/contents/images/3840x2160.jpg");
desktop.reloadConfig();
