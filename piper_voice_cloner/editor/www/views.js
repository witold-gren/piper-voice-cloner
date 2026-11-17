// The parts of the middle column. Each stage of the editor adds its views here.
import "./views-train.js";
import "./views-clone.js";
import "./views-base.js";
import "./views-settings.js";

// the editor may have drawn "comes later" before these modules arrived
document.querySelector("pvc-editor")?.requestUpdate();
