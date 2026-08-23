// voice.js — Ovozli xabar yozish (STT) va javobni ovozda o'qish (TTS)
// Hech qanday to'lovli API talab qilmaydi — brauzerning o'z Web Speech
// API'sidan foydalanadi. To'liq qo'llab-quvvatlash: Chrome/Edge.
// Firefox/Safari'da qisman ishlashi yoki umuman ishlamasligi mumkin.

(function () {
  const micButton = document.getElementById("mic-button");
  const inputEl = document.getElementById("message-input");

  const SpeechRecognitionImpl = window.SpeechRecognition || window.webkitSpeechRecognition;

  if (SpeechRecognitionImpl && micButton && inputEl) {
    micButton.hidden = false;
    const recognition = new SpeechRecognitionImpl();
    recognition.lang = "uz-UZ"; // Agar tanib olmasa "ru-RU" yoki "en-US" sinab ko'ring
    recognition.interimResults = false;

    let isListening = false;

    micButton.addEventListener("click", () => {
      if (isListening) {
        recognition.stop();
        return;
      }
      recognition.start();
    });

    recognition.addEventListener("start", () => {
      isListening = true;
      micButton.classList.add("mic-button--active");
    });

    recognition.addEventListener("end", () => {
      isListening = false;
      micButton.classList.remove("mic-button--active");
    });

    recognition.addEventListener("result", (event) => {
      const transcript = Array.from(event.results)
        .map((result) => result[0].transcript)
        .join(" ");
      inputEl.value = transcript;
      inputEl.dispatchEvent(new Event("input"));
    });

    recognition.addEventListener("error", (event) => {
      console.warn("Ovozni tanish xatosi:", event.error);
      isListening = false;
      micButton.classList.remove("mic-button--active");
    });
  }

  window.speakText = function speakText(text) {
    if (!window.speechSynthesis) return;
    const utterance = new SpeechSynthesisUtterance(text);
    utterance.lang = "uz-UZ";
    window.speechSynthesis.cancel();
    window.speechSynthesis.speak(utterance);
  };
})();
