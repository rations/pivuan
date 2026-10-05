#!/usr/bin/env python3
"""Report which standard icon names the theme covers.

Compares mapping/icons.toml (plus the MIME database icons build_theme.py adds)
with the names of the freedesktop Icon Naming Specification. Names the theme
lacks are taken from the inherited themes (INHERITS in config.mk) instead.

Usage: coverage.py --haiku-src DIR --build DIR [--missing]
"""

import argparse
from pathlib import Path

from build_theme import REPO, Sources, load_mapping

# Icon Naming Specification 0.8.90, without the animation and weather names.
SPEC = {
    "actions": """address-book-new application-exit appointment-new call-start call-stop
        contact-new document-new document-open document-open-recent document-page-setup
        document-print document-print-preview document-properties document-revert
        document-save document-save-as document-send edit-clear edit-copy edit-cut
        edit-delete edit-find edit-find-replace edit-paste edit-redo edit-select-all
        edit-undo folder-new format-indent-less format-indent-more format-justify-center
        format-justify-fill format-justify-left format-justify-right
        format-text-direction-ltr format-text-direction-rtl format-text-bold
        format-text-italic format-text-underline format-text-strikethrough go-bottom
        go-down go-first go-home go-jump go-last go-next go-previous go-top go-up
        help-about help-contents help-faq insert-image insert-link insert-object
        insert-text list-add list-remove mail-forward mail-mark-important mail-mark-junk
        mail-mark-notjunk mail-mark-read mail-mark-unread mail-message-new
        mail-reply-all mail-reply-sender mail-send mail-send-receive media-eject
        media-playback-pause media-playback-start media-playback-stop media-record
        media-seek-backward media-seek-forward media-skip-backward media-skip-forward
        object-flip-horizontal object-flip-vertical object-rotate-left
        object-rotate-right process-stop system-lock-screen system-log-out system-run
        system-search system-reboot system-shutdown tools-check-spelling
        view-fullscreen view-refresh view-restore view-sort-ascending
        view-sort-descending window-close window-new zoom-fit-best zoom-in
        zoom-original zoom-out""",
    "apps": """accessories-calculator accessories-character-map accessories-dictionary
        accessories-text-editor help-browser multimedia-volume-control
        preferences-desktop-accessibility preferences-desktop-font
        preferences-desktop-keyboard preferences-desktop-locale
        preferences-desktop-multimedia preferences-desktop-screensaver
        preferences-desktop-theme preferences-desktop-wallpaper system-file-manager
        system-software-install system-software-update utilities-system-monitor
        utilities-terminal""",
    "categories": """applications-accessories applications-development
        applications-engineering applications-games applications-graphics
        applications-internet applications-multimedia applications-office
        applications-other applications-science applications-system
        applications-utilities preferences-desktop preferences-desktop-peripherals
        preferences-desktop-personal preferences-other preferences-system
        preferences-system-network system-help""",
    "devices": """audio-card audio-input-microphone battery camera-photo camera-video
        camera-web computer drive-harddisk drive-optical drive-removable-media
        input-gaming input-keyboard input-mouse input-tablet media-flash media-floppy
        media-optical media-tape modem multimedia-player network-wired
        network-wireless pda phone printer scanner video-display""",
    "emblems": """emblem-default emblem-documents emblem-downloads emblem-favorite
        emblem-important emblem-mail emblem-photos emblem-readonly emblem-shared
        emblem-symbolic-link emblem-synchronized emblem-system emblem-unreadable""",
    "mimetypes": """application-x-executable audio-x-generic font-x-generic
        image-x-generic package-x-generic text-html text-x-generic
        text-x-generic-template text-x-script video-x-generic x-office-address-book
        x-office-calendar x-office-document x-office-presentation
        x-office-spreadsheet""",
    "places": """folder folder-remote network-server network-workgroup start-here
        user-bookmarks user-desktop user-home user-trash""",
    "status": """appointment-missed appointment-soon audio-volume-high audio-volume-low
        audio-volume-medium audio-volume-muted battery-caution battery-low dialog-error
        dialog-information dialog-password dialog-question dialog-warning
        folder-drag-accept folder-open folder-visiting image-loading image-missing
        mail-attachment mail-unread mail-read mail-replied mail-signed
        mail-signed-verified media-playlist-repeat media-playlist-shuffle network-error
        network-idle network-offline network-receive network-transmit
        network-transmit-receive printer-error printer-printing security-high
        security-medium security-low software-update-available software-update-urgent
        sync-error sync-synchronizing task-due task-past-due user-available user-away
        user-idle user-offline user-trash-full""",
}


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--haiku-src", required=True)
    ap.add_argument("--build", required=True)
    ap.add_argument("--mapping", default=str(REPO / "mapping/icons.toml"))
    args = ap.parse_args()

    mapping = load_mapping(Sources(args.haiku_src, Path(args.build)), args.mapping)
    have = {name for names in mapping.values() for name in names}
    total_have = total = 0
    for context, names in SPEC.items():
        names = names.split()
        missing = [n for n in names if n not in have]
        covered = len(names) - len(missing)
        total_have, total = total_have + covered, total + len(names)
        print(f"{context:11} {covered:3}/{len(names):<3} missing: {' '.join(missing) or '-'}")
    extra = len(have) - total_have
    print(f"{'total':11} {total_have:3}/{total:<3} standard names, plus {extra} other names "
          "(app ids, MIME types)")


if __name__ == "__main__":
    main()
