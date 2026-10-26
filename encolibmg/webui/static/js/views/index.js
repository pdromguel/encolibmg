// Screen registry + the order of the top navigation (keys 1–6).
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
  { name: "home", label: "Início" },
  { name: "add", label: "Adicionar" },
  { name: "library", label: "Biblioteca" },
  { name: "check", label: "Verificar" },
  { name: "import", label: "Importar" },
  { name: "visual", label: "Visual e som" },
];
