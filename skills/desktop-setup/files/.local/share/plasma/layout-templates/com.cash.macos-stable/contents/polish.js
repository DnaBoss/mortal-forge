// Apply the non-destructive finishing touches to an existing macOS Stable layout.

const currentPanels = panels();
for (let panelIndex = 0; panelIndex < currentPanels.length; panelIndex += 1) {
    const currentPanel = currentPanels[panelIndex];
    const widgets = currentPanel.widgets();
    let dockHasTrash = false;

    for (let widgetIndex = 0; widgetIndex < widgets.length; widgetIndex += 1) {
        const widget = widgets[widgetIndex];

        if (widget.type === "org.kde.plasma.systemtray") {
            widget.currentConfigGroup = ["General"];
            widget.writeConfig("hiddenItems", [
                "org.kde.plasma.battery",
                "org.kde.plasma.brightness",
                "org.kde.plasma.clipboard",
                "org.kde.plasma.devicenotifier",
                "org.kde.plasma.printmanager",
                "org.kde.kscreen"
            ]);
            widget.reloadConfig();
        }

        if (widget.type === "org.kde.plasma.digitalclock") {
            widget.currentConfigGroup = ["Appearance"];
            widget.writeConfig("showDate", false);
            widget.writeConfig("showSeconds", false);
            widget.writeConfig("fontWeight", 400);
            widget.reloadConfig();
        }

        if (widget.type === "org.kde.plasma.showdesktop") {
            widget.remove();
        }

        if (widget.type === "org.kde.plasma.trash") {
            dockHasTrash = true;
        }
    }

    if (currentPanel.location === "bottom" && !dockHasTrash) {
        currentPanel.addWidget("org.kde.plasma.trash");
    }
}
