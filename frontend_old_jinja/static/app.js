// Design doc 3.3/3.4/3.5: eligibility checker, subscribe/unsubscribe, and
// result search all happen inline via fetch -- no page navigation, per
// section 3.2's "shown inline without a page navigation" requirement.

(function () {
  const API = window.API_BASE_URL;

  function showResult(el, text, cssClass) {
    el.hidden = false;
    el.textContent = text;
    el.className = el.className.replace(/verdict-\S+/g, "").trim();
    if (cssClass) el.classList.add(cssClass);
  }

  const eligibilityForm = document.getElementById("eligibility-form");
  if (eligibilityForm) {
    eligibilityForm.addEventListener("submit", async (e) => {
      e.preventDefault();
      const resultEl = document.getElementById("eligibility-result");
      const formData = new FormData(eligibilityForm);
      const lang = window.i18n.currentLang();

      try {
        const resp = await fetch(`${API}/eligibility-check`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            exam_id: Number(eligibilityForm.dataset.examId),
            degree: formData.get("degree"),
            age: Number(formData.get("age")),
            category: formData.get("category"),
          }),
        });
        const data = await resp.json();

        if (data.eligible === true) {
          showResult(resultEl, (lang === "hi" ? "✓ आप पात्र हैं। " : "✓ You are eligible. ") + data.reason, "verdict-eligible");
        } else if (data.eligible === false) {
          showResult(resultEl, (lang === "hi" ? "✗ आप पात्र नहीं हैं। " : "✗ You are not eligible. ") + data.reason, "verdict-not-eligible");
        } else {
          showResult(resultEl, data.reason, "verdict-unknown");
        }
      } catch (err) {
        showResult(resultEl, window.i18n.currentLang() === "hi" ? "जांच नहीं हो सकी, फिर कोशिश करें।" : "Couldn't check right now, please try again.", "verdict-unknown");
      }
    });
  }

  const subscribeForm = document.getElementById("subscribe-form");
  if (subscribeForm) {
    subscribeForm.addEventListener("submit", async (e) => {
      e.preventDefault();
      const submitter = e.submitter;
      const action = submitter && submitter.dataset.action === "unsubscribe" ? "unsubscribe" : "subscribe";
      const resultEl = document.getElementById("subscribe-result");
      const formData = new FormData(subscribeForm);
      const lang = window.i18n.currentLang();

      try {
        const resp = await fetch(`${API}/${action}`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            exam_id: Number(subscribeForm.dataset.examId),
            phone_number: formData.get("phone_number"),
          }),
        });

        if (!resp.ok) {
          const err = await resp.json().catch(() => ({}));
          showResult(resultEl, err.detail || (lang === "hi" ? "कुछ गलत हो गया।" : "Something went wrong."), "verdict-unknown");
          return;
        }

        if (action === "subscribe") {
          showResult(resultEl, lang === "hi" ? "✓ आप सब्सक्राइब हो गए हैं। पुष्टि व्हाट्सएप पर भेजी जाएगी।" : "✓ You're subscribed. A confirmation will be sent on WhatsApp.", "verdict-eligible");
        } else {
          showResult(resultEl, lang === "hi" ? "अनसब्सक्राइब हो गया।" : "Unsubscribed.", "verdict-unknown");
        }
      } catch (err) {
        showResult(resultEl, lang === "hi" ? "कुछ गलत हो गया, फिर कोशिश करें।" : "Something went wrong, please try again.", "verdict-unknown");
      }
    });
  }

  const resultForm = document.getElementById("result-form");
  if (resultForm) {
    resultForm.addEventListener("submit", async (e) => {
      e.preventDefault();
      const resultEl = document.getElementById("result-search-result");
      const formData = new FormData(resultForm);
      const rollNumber = formData.get("roll_number");
      const examId = resultForm.dataset.examId;
      const lang = window.i18n.currentLang();

      try {
        const resp = await fetch(`${API}/results?exam_id=${encodeURIComponent(examId)}&roll_number=${encodeURIComponent(rollNumber)}`);
        const data = await resp.json();

        if (!data.found) {
          showResult(resultEl, lang === "hi" ? "इस रोल नंबर के लिए कोई परिणाम नहीं मिला।" : "No result found for this roll number.", "verdict-unknown");
          return;
        }

        let text = `${lang === "hi" ? "स्थिति" : "Status"}: ${data.status || "—"}`;
        if (data.rank) text += ` · ${lang === "hi" ? "रैंक" : "Rank"}: ${data.rank}`;
        showResult(resultEl, text, "verdict-eligible");
      } catch (err) {
        showResult(resultEl, lang === "hi" ? "खोज नहीं हो सकी, फिर कोशिश करें।" : "Couldn't search right now, please try again.", "verdict-unknown");
      }
    });
  }

  // Client-side filter -- the exam list is small (single-digit count in
  // Phase 0), so a backend search endpoint would be premature; this can
  // move server-side once the list actually grows.
  const searchInput = document.getElementById("exam-search");
  if (searchInput) {
    const cards = Array.from(document.querySelectorAll(".exam-card"));
    const noResultsEl = document.getElementById("no-search-results");
    searchInput.addEventListener("input", () => {
      const query = searchInput.value.trim().toLowerCase();
      let visibleCount = 0;
      cards.forEach((card) => {
        const matches = card.dataset.searchText.toLowerCase().includes(query);
        card.hidden = !matches;
        if (matches) visibleCount += 1;
      });
      if (noResultsEl) noResultsEl.hidden = visibleCount !== 0;
    });
  }

  const callbackToggle = document.getElementById("callback-toggle");
  const callbackForm = document.getElementById("callback-form");
  if (callbackToggle && callbackForm) {
    callbackToggle.addEventListener("click", () => {
      callbackForm.hidden = !callbackForm.hidden;
    });

    callbackForm.addEventListener("submit", async (e) => {
      e.preventDefault();
      const resultEl = document.getElementById("callback-result");
      const formData = new FormData(callbackForm);
      const examId = callbackForm.dataset.examId;
      const lang = window.i18n.currentLang();

      try {
        const resp = await fetch(`${API}/callback-request`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            phone_number: formData.get("phone_number"),
            exam_id: examId ? Number(examId) : null,
          }),
        });

        if (!resp.ok) {
          showResult(resultEl, window.i18n.DICTIONARY.callback_error[lang], "verdict-unknown");
          return;
        }

        showResult(resultEl, window.i18n.DICTIONARY.callback_success[lang], "verdict-eligible");
        callbackForm.hidden = true;
        callbackForm.reset();
      } catch (err) {
        showResult(resultEl, window.i18n.DICTIONARY.callback_error[lang], "verdict-unknown");
      }
    });
  }
})();
