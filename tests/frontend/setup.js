// Vitest setup: jest-dom matchers + React + ReactDOM globals so app.jsx
// (which references window.React/window.ReactDOM) can be imported as a module.
import "@testing-library/jest-dom/vitest";
import React from "react";
import ReactDOM from "react-dom";
import * as ReactDOMClient from "react-dom/client";

// app.jsx uses bare globals (`React`, `ReactDOM`). Ensure they exist on window.
globalThis.React = React;
globalThis.ReactDOM = { ...ReactDOM, ...ReactDOMClient };
window.React = React;
window.ReactDOM = globalThis.ReactDOM;
