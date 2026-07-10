// Briwell landing — shared behavior. No dependencies: IntersectionObserver
// reveals, scroll-scrubbed pipeline rail, and a seamless headline ticker.
(function () {
  "use strict";

  var reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  // --- reveal on scroll -----------------------------------------------------
  var revealEls = document.querySelectorAll(".reveal");
  if ("IntersectionObserver" in window && !reduceMotion) {
    var io = new IntersectionObserver(
      function (entries) {
        entries.forEach(function (entry) {
          if (entry.isIntersecting) {
            entry.target.classList.add("in");
            io.unobserve(entry.target);
          }
        });
      },
      { threshold: 0.14, rootMargin: "0px 0px -40px 0px" }
    );
    revealEls.forEach(function (el) { io.observe(el); });
  } else {
    revealEls.forEach(function (el) { el.classList.add("in"); });
  }

  // --- ticker: duplicate the track so the loop is seamless -------------------
  document.querySelectorAll(".ticker").forEach(function (ticker) {
    var track = ticker.querySelector(".ticker-track");
    if (!track) return;
    var clone = track.cloneNode(true);
    clone.setAttribute("aria-hidden", "true");
    ticker.appendChild(clone);
  });

  // --- pipeline: fill the rail + light nodes as they pass mid-viewport -------
  var pipeline = document.querySelector(".pipeline");
  if (pipeline) {
    var fill = pipeline.querySelector(".pipe-rail-fill");
    var steps = Array.prototype.slice.call(pipeline.querySelectorAll(".pipe-step"));
    var railTicking = false;

    var updateRail = function () {
      railTicking = false;
      var rect = pipeline.getBoundingClientRect();
      var mid = window.innerHeight * 0.55;
      var progress = (mid - rect.top) / rect.height;
      progress = Math.max(0, Math.min(1, progress));
      if (fill) fill.style.height = (progress * 100).toFixed(2) + "%";
      steps.forEach(function (step) {
        var sRect = step.getBoundingClientRect();
        step.classList.toggle("lit", sRect.top + sRect.height * 0.35 < mid);
      });
    };

    var onScroll = function () {
      if (!railTicking) {
        railTicking = true;
        window.requestAnimationFrame(updateRail);
      }
    };

    if (reduceMotion) {
      if (fill) fill.style.height = "100%";
      steps.forEach(function (step) { step.classList.add("lit"); });
    } else {
      window.addEventListener("scroll", onScroll, { passive: true });
      window.addEventListener("resize", onScroll);
      updateRail();
    }
  }

  // NOTE: the former "live market pulse" fetch was removed on purpose
  // (2026-07-10): /trends/news requires operator-tier roles, so a public
  // landing page can never call it. The ticker keeps its baked headlines.
})();
