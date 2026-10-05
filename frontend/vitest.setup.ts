import "@testing-library/jest-dom";

// jsdom does not implement scrollIntoView; stub it so components that call it don't throw.
window.HTMLElement.prototype.scrollIntoView = function () {};
