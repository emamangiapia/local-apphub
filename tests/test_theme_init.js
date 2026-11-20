"use strict";

const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const script = fs.readFileSync(path.join(__dirname, "../apphub/static/theme-init.js"), "utf8");

function start({ saved = null, blocked = false } = {}) {
  const store = new Map(saved === null ? [] : [["local-apphub-theme", saved]]);
  const callbacks = {};
  const makeButton = (themeChoice) => ({
    dataset: { themeChoice },
    attributes: {},
    classes: new Set(),
    listeners: {},
    setAttribute(key, value) { this.attributes[key] = value; },
    classList: {
      toggle(name, active) {
        if (active) this.target.classes.add(name);
        else this.target.classes.delete(name);
      },
    },
    addEventListener(name, callback) { this.listeners[name] = callback; },
  });
  const buttons = [makeButton("retro"), makeButton("liquid"), makeButton("retro")];
  for (const button of buttons) button.classList.target = button;
  const themeColor = { content: null, setAttribute(key, value) { if (key === "content") this.content = value; } };
  const document = {
    documentElement: { dataset: {}, style: {} },
    querySelectorAll() { return buttons; },
    querySelector(selector) { return selector === 'meta[name="theme-color"]' ? themeColor : null; },
    addEventListener(name, fn) { callbacks[name] = fn; },
  };
  const localStorage = {
    getItem(key) { if (blocked) throw new Error("blocked"); return store.get(key); },
    setItem(key, value) { if (blocked) throw new Error("blocked"); store.set(key, value); },
  };
  vm.runInNewContext(script, { document, localStorage });
  callbacks.DOMContentLoaded();
  return { document, buttons, store, themeColor };
}

{
  const { document, buttons, themeColor } = start();
  assert.equal(document.documentElement.dataset.theme, "retro");
  assert.equal(document.documentElement.style.colorScheme, "dark");
  assert.equal(themeColor.content, "#11142a");
  assert.equal(buttons[0].attributes["aria-pressed"], "true");
  assert.equal(buttons[1].attributes["aria-pressed"], "false");
}

{
  const { document, buttons, store, themeColor } = start({ saved: "liquid" });
  assert.equal(document.documentElement.dataset.theme, "liquid");
  assert.equal(document.documentElement.style.colorScheme, "light");
  assert.equal(themeColor.content, "#e8effa");
  buttons[0].listeners.click();
  assert.equal(document.documentElement.dataset.theme, "retro");
  assert.equal(store.get("local-apphub-theme"), "retro");
  buttons[1].listeners.click();
  assert.equal(store.get("local-apphub-theme"), "liquid");
  assert.equal(buttons[0].attributes["aria-pressed"], "false");
  assert.equal(buttons[1].attributes["aria-pressed"], "true");
  assert.equal(buttons[2].attributes["aria-pressed"], "false");
}

{
  const { document, buttons } = start({ blocked: true });
  buttons[1].listeners.click();
  assert.equal(document.documentElement.dataset.theme, "liquid");
}

process.stdout.write("Theme preference tests: OK\n");
