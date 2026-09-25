/* DoorMath site: accessible screenshot lightbox. */
(function () {
  "use strict";
  var dialog = document.getElementById("lightbox");
  var figure = document.getElementById("lb-figure");
  var caption = document.getElementById("lb-caption");
  var closeBtn = document.getElementById("lb-close");
  if (!dialog || !figure || typeof dialog.showModal !== "function") return; // links still open the image

  var img = document.createElement("img");
  img.id = "lb-img";
  img.decoding = "async";
  figure.insertBefore(img, caption);

  var trigger = null;

  function open(link) {
    var thumb = link.querySelector("img");
    trigger = link;
    img.removeAttribute("width");
    img.removeAttribute("height");
    img.src = link.getAttribute("href");
    img.alt = thumb ? thumb.alt : "";
    caption.textContent = link.getAttribute("data-caption") || "";
    dialog.showModal();
    closeBtn.focus();
    document.documentElement.style.overflow = "hidden";
  }

  function close() {
    if (dialog.open) dialog.close();
  }

  dialog.addEventListener("close", function () {
    document.documentElement.style.overflow = "";
    img.removeAttribute("src");
    if (trigger && typeof trigger.focus === "function") trigger.focus();
    trigger = null;
  });

  document.addEventListener("click", function (e) {
    var link = e.target.closest ? e.target.closest("a.zoom") : null;
    if (!link) return;
    if (e.defaultPrevented || e.button !== 0 || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return;
    e.preventDefault();
    open(link);
  });

  closeBtn.addEventListener("click", close);

  // Click outside the image (on the backdrop / padding) closes. Esc is handled natively by <dialog>.
  dialog.addEventListener("click", function (e) {
    if (e.target === dialog || e.target.classList.contains("lb-inner") || e.target === figure) close();
  });
})();
