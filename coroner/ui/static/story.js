// Keyboard shortcuts and focus of the guided story. Links and buttons keep their native behavior.
(function () {
    "use strict";

    function isFormControl(element) {
        if (!element) {
            return false;
        }
        var tag = element.tagName;
        return tag === "INPUT" || tag === "SELECT" || tag === "TEXTAREA" || tag === "BUTTON" || element.isContentEditable;
    }

    document.addEventListener("keydown", function (event) {
        if (event.defaultPrevented) {
            return;
        }
        if (event.ctrlKey || event.metaKey || event.altKey || event.shiftKey) {
            return;
        }
        var active = document.activeElement;
        if (isFormControl(active)) {
            return;
        }
        // A scrollable listing region uses the arrow keys to scroll.
        if (active && active.closest && active.closest('[role="region"]')) {
            return;
        }
        var link = null;
        if (event.key === "ArrowRight") {
            link = document.querySelector("a.story-next");
        } else if (event.key === "ArrowLeft") {
            link = document.querySelector("a.story-back");
        } else if (event.key === "Escape") {
            window.location.href = "/";
            return;
        }
        if (link) {
            event.preventDefault();
            link.click();
        }
    });

    // After a step is swapped in, move focus to its heading so keyboard and screen reader
    // visitors are not left on a removed element.
    document.body.addEventListener("htmx:afterSwap", function (event) {
        var target = event.detail && event.detail.target;
        if (target && target.id === "story-content") {
            var heading = document.getElementById("step-heading");
            if (heading) {
                heading.focus();
            }
        }
    });
})();
