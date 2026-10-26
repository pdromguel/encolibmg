// Screen registry + the order of the top navigation (keys 1–6). Labels are i18n keys.
import { home } from "./home.js";
import { add } from "./add.js";
import { library } from "./library.js";
import { check } from "./check.js";
import { importer } from "./import.js";
import { visual } from "./visual.js";
import { sync } from "./sync.js";
import { guide } from "./guide.js";

export const screens = { home, add, library, check, import: importer, visual, sync, guide };

export const NAV = [
  { name: "home", label: "ui.nav.home" },
  { name: "add", label: "ui.nav.add" },
  { name: "library", label: "ui.nav.library" },
  { name: "check", label: "ui.nav.check" },
  { name: "import", label: "ui.nav.import" },
  { name: "visual", label: "ui.nav.visual" },
];
