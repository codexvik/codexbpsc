// Design doc section 1.4: Hindi/English toggle on every page, no reload,
// defaulting to Hindi for first-time visitors. Plain JS, no framework --
// this + the two-language-spans-in-DOM approach for status badges (see
// style.css .lang-en/.lang-hi) is the whole i18n mechanism.

(function () {
  const DICTIONARY = {
    site_name: { en: "Bihar Exam Alerts", hi: "बिहार परीक्षा अलर्ट" },
    footer_note: {
      en: "Every claim on this site links to an independent, verifiable source.",
      hi: "इस साइट पर हर जानकारी एक स्वतंत्र, सत्यापन योग्य स्रोत से जुड़ी है।",
    },
    api_error: { en: "Couldn't load exams right now. Please try again shortly.", hi: "अभी परीक्षाएं लोड नहीं हो सकीं। कृपया थोड़ी देर बाद पुनः प्रयास करें।" },
    no_exams: { en: "No exams available yet.", hi: "अभी कोई परीक्षा उपलब्ध नहीं है।" },
    advt_no: { en: "Advt. No.", hi: "विज्ञापन संख्या" },
    vacancies: { en: "Vacancies", hi: "रिक्तियां" },
    latest_change: { en: "Latest", hi: "हाल में" },
    back_to_exams: { en: "← Back to exams", hi: "← परीक्षाओं पर वापस जाएं" },
    key_dates: { en: "Key Dates", hi: "महत्वपूर्ण तिथियां" },
    eligibility_title: { en: "Check Your Eligibility", hi: "अपनी पात्रता जांचें" },
    degree_label: { en: "Highest Qualification", hi: "उच्चतम शैक्षणिक योग्यता" },
    age_label: { en: "Age", hi: "आयु" },
    category_label: { en: "Category", hi: "श्रेणी" },
    category_cert_note: {
      en: "Certificate requirements for your category will be shown here once available.",
      hi: "आपकी श्रेणी के लिए प्रमाण पत्र की जानकारी उपलब्ध होते ही यहां दिखाई जाएगी।",
    },
    check_eligibility: { en: "Check Eligibility", hi: "पात्रता जांचें" },
    subscribe_title: { en: "Get WhatsApp Alerts", hi: "व्हाट्सएप अलर्ट प्राप्त करें" },
    phone_label: { en: "Phone Number", hi: "फ़ोन नंबर" },
    subscribe_btn: { en: "Subscribe", hi: "सब्सक्राइब करें" },
    unsubscribe_btn: { en: "Unsubscribe", hi: "अनसब्सक्राइब करें" },
    notices_title: { en: "Notice Feed", hi: "सूचना फ़ीड" },
    no_notices: { en: "No notices yet.", hi: "अभी तक कोई सूचना नहीं है।" },
    detected_on: { en: "Detected", hi: "पता चला" },
    effective_date: { en: "Effective", hi: "प्रभावी" },
    verified_archive: { en: "✓ Verified archive", hi: "✓ सत्यापित संग्रह" },
    not_yet_archived: { en: "Not yet independently archived", hi: "अभी तक स्वतंत्र रूप से संग्रहीत नहीं" },
    see_official: { en: "See official notice", hi: "आधिकारिक सूचना देखें" },
    result_search_title: { en: "Search Your Result", hi: "अपना परिणाम खोजें" },
    roll_number_label: { en: "Roll Number", hi: "रोल नंबर" },
    search_btn: { en: "Search", hi: "खोजें" },
    search_placeholder: { en: "Search exams...", hi: "परीक्षा खोजें..." },
    no_search_results: { en: "No exams match your search.", hi: "आपकी खोज से कोई परीक्षा नहीं मिली।" },
    request_callback: { en: "Request a Callback", hi: "कॉलबैक का अनुरोध करें" },
    submit_btn: { en: "Submit", hi: "जमा करें" },
    callback_success: { en: "Thanks -- we'll call you back soon.", hi: "धन्यवाद -- हम जल्द ही आपको कॉल करेंगे।" },
    callback_error: { en: "Couldn't submit right now, please try again.", hi: "अभी जमा नहीं हो सका, कृपया फिर कोशिश करें।" },
    top_notices_title: { en: "Recent Notices", hi: "हाल की सूचनाएं" },
    trust_score_label: { en: "Trust Score", hi: "ट्रस्ट स्कोर" },
    coming_soon: { en: "Coming soon", hi: "जल्द आ रहा है" },
    stats_title: { en: "Exam Stats", hi: "परीक्षा आंकड़े" },
    stats_attendance: { en: "Candidates last year", hi: "पिछले वर्ष के अभ्यर्थी" },
    stats_vacancies_filled: { en: "Vacancies filled", hi: "भरी गई रिक्तियां" },
    stats_unavailable: { en: "Not yet available", hi: "अभी उपलब्ध नहीं" },
    partner_space_label: { en: "Partner Space", hi: "पार्टनर स्पेस" },
    partner_space_placeholder: { en: "Reserved -- not active yet", hi: "आरक्षित -- अभी सक्रिय नहीं" },
  };

  function applyLang(lang) {
    document.documentElement.setAttribute("data-lang", lang);
    document.querySelectorAll("[data-i18n]").forEach((el) => {
      const entry = DICTIONARY[el.getAttribute("data-i18n")];
      if (entry && entry[lang]) el.textContent = entry[lang];
    });
    document.querySelectorAll("[data-i18n-placeholder]").forEach((el) => {
      const entry = DICTIONARY[el.getAttribute("data-i18n-placeholder")];
      if (entry && entry[lang]) el.setAttribute("placeholder", entry[lang]);
    });
    localStorage.setItem("lang", lang);
  }

  function currentLang() {
    return localStorage.getItem("lang") || "hi"; // design doc: default Hindi for first-time mobile visitors
  }

  window.i18n = { applyLang, currentLang, DICTIONARY };

  document.addEventListener("DOMContentLoaded", () => {
    applyLang(currentLang());
    const toggle = document.getElementById("lang-toggle");
    if (toggle) {
      toggle.addEventListener("click", () => {
        applyLang(currentLang() === "hi" ? "en" : "hi");
      });
    }
  });
})();
