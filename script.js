/* ------------------------------------------------------------------
   Wires up the gift box, builds the cards from gifts.js, and handles
   the reveal + redeem popup. You normally don't need to edit this.
   ------------------------------------------------------------------ */

document.addEventListener("DOMContentLoaded", () => {
  spawnHearts();
  applyConfig();

  const giftbox = document.getElementById("giftbox");
  giftbox.addEventListener("click", openBox);
});

/* ---------- floating hearts ---------- */
function spawnHearts() {
  const layer = document.querySelector(".hearts");
  const emojis = ["💛", "💕", "✨", "🤍", "💗"];
  const count = 14;
  for (let i = 0; i < count; i++) {
    const h = document.createElement("span");
    h.textContent = emojis[i % emojis.length];
    h.style.left = Math.random() * 100 + "vw";
    h.style.fontSize = 12 + Math.random() * 22 + "px";
    h.style.animationDuration = 9 + Math.random() * 12 + "s";
    h.style.animationDelay = Math.random() * 12 + "s";
    layer.appendChild(h);
  }
}

/* ---------- config text ---------- */
function applyConfig() {
  if (CONFIG.photo) {
    document.getElementById("photo").src = CONFIG.photo;
    document.getElementById("photoFrame").hidden = false;
  }
  document.getElementById("boxEyebrow").textContent = "For " + CONFIG.recipientName;
  document.getElementById("boxTitle").textContent = CONFIG.openingTitle;
  document.getElementById("boxHint").textContent = CONFIG.openingSubtitle;
  document.getElementById("giftsGreeting").textContent =
    "Hi " + CONFIG.recipientName + " 💛";
  document.getElementById("loveNote").textContent = CONFIG.loveNote;
  document.getElementById("signed").textContent = "— " + CONFIG.fromName;
}

/* ---------- open the box -> show gifts ---------- */
function openBox() {
  const giftbox = document.getElementById("giftbox");
  if (giftbox.classList.contains("is-open")) return;

  giftbox.classList.add("is-open");
  burst();

  const boxScreen = document.getElementById("boxScreen");
  const giftsScreen = document.getElementById("giftsScreen");

  setTimeout(() => {
    boxScreen.classList.add("fade-out");
    setTimeout(() => {
      boxScreen.hidden = true;
      giftsScreen.hidden = false;
      giftsScreen.classList.add("fade-in");
      buildCards();
    }, 480);
  }, 650);
}

/* confetti-ish burst of hearts on open */
function burst() {
  const layer = document.querySelector(".hearts");
  const emojis = ["💛", "💕", "✨", "🎉", "💗"];
  for (let i = 0; i < 18; i++) {
    const h = document.createElement("span");
    h.textContent = emojis[i % emojis.length];
    h.style.left = 35 + Math.random() * 30 + "vw";
    h.style.bottom = "45vh";
    h.style.fontSize = 16 + Math.random() * 20 + "px";
    h.style.animationDuration = 4 + Math.random() * 4 + "s";
    h.style.animationDelay = "0s";
    layer.appendChild(h);
    setTimeout(() => h.remove(), 8000);
  }
}

/* ---------- build the gift cards ---------- */
const ACCENTS = {
  rose:    ["var(--rose-1)", "var(--rose-2)"],
  violet:  ["var(--violet-1)", "var(--violet-2)"],
  amber:   ["var(--amber-1)", "var(--amber-2)"],
  emerald: ["var(--emerald-1)", "var(--emerald-2)"],
};

function buildCards() {
  const grid = document.getElementById("giftGrid");
  grid.innerHTML = "";

  GIFTS.forEach((gift, i) => {
    const [c1, c2] = ACCENTS[gift.accent] || ACCENTS.rose;

    const card = document.createElement("button");
    card.className = "card status-" + gift.status;
    card.style.setProperty("--c1", c1);
    card.style.setProperty("--c2", c2);
    card.style.animationDelay = i * 0.09 + "s";

    const isSoon = gift.status === "soon";
    const isRedeemed = gift.status === "redeemed";

    const flag = isSoon
      ? '<span class="flag soon">Coming soon</span>'
      : isRedeemed
      ? '<span class="flag redeemed">Used</span>'
      : "";

    const peek = isSoon ? "A surprise still wrapped…" : "Tap to reveal";

    const backBtn = isSoon
      ? '<span class="redeem-btn" style="opacity:.6;cursor:default">Soon 💫</span>'
      : isRedeemed
      ? '<span class="redeem-btn" style="opacity:.6;cursor:default">Redeemed</span>'
      : '<span class="redeem-btn">Redeem 💛</span>';

    const stamp = isRedeemed ? '<span class="stamp">REDEEMED</span>' : "";

    card.innerHTML = `
      ${flag}
      <div class="card__inner">
        <div class="card__face card__front">
          <span class="q">🎁</span>
          <span class="tap">Gift ${i + 1}</span>
          <span class="peek">${peek}</span>
        </div>
        <div class="card__face card__back">
          ${stamp}
          <span class="emoji">${gift.emoji}</span>
          <span class="value">${gift.value}</span>
          <h3>${gift.title}</h3>
          <span class="sub">${gift.subtitle}</span>
          ${backBtn}
        </div>
      </div>
    `;

    card.addEventListener("click", () => {
      if (!card.classList.contains("is-flipped")) {
        card.classList.add("is-flipped");
        return;
      }
      // already revealed: tapping redeem opens the popup (unless soon)
      if (gift.status === "available") openModal(gift);
    });

    grid.appendChild(card);
  });
}

/* ---------- redeem modal ---------- */
function openModal(gift) {
  document.getElementById("modalEmoji").textContent = gift.emoji;
  document.getElementById("modalTitle").textContent = gift.title;
  document.getElementById("modalDesc").textContent = gift.description;
  document.getElementById("modalCode").textContent = gift.code;

  const modal = document.getElementById("modal");
  modal.hidden = false;

  modal.querySelectorAll("[data-close]").forEach((el) => {
    el.onclick = () => (modal.hidden = true);
  });
  document.onkeydown = (e) => {
    if (e.key === "Escape") modal.hidden = true;
  };
}
