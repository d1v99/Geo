/* =========================================================================
   YOUR GIFTS — edit this file to add, remove, or change gifts.
   This is the ONLY file you normally need to touch.

   How to add a new gift:
   1. Copy one of the { ... } blocks below.
   2. Paste it inside the [ ] list (separate each block with a comma).
   3. Change the words. Save the file. Done.

   Tips:
   - "status" can be:  "available"  (ready to redeem)
                       "redeemed"   (already used — shows a stamp)
                       "soon"       (coming soon — stays a mystery)
   - "emoji" is just the little icon shown on the card.
   - "code" is the voucher code she can show you to redeem it.
   ========================================================================= */

const CONFIG = {
  // Who this is for — shows on the front of the gift box.
  recipientName: "Beautiful",

  // Who it's from.
  fromName: "Me",

  // The big line on the opening screen.
  openingTitle: "A little something for you",
  openingSubtitle: "Tap the box to open your surprise",

  // The sweet note shown at the bottom of the page.
  loveNote:
    "Just a few little ways to spoil you. Pick whichever one you want, " +
    "whenever you want it, and it's on me. More surprises will keep " +
    "showing up here. I love you. 💛",
};

const GIFTS = [
  {
    emoji: "💆‍♀️",
    title: "A Relaxing Massage",
    subtitle: "Full hour, fully on me",
    value: "1 Massage",
    description:
      "Book your next massage anywhere you like — I've got the bill. " +
      "Go relax, you deserve it.",
    code: "RELAX-01",
    accent: "rose",
    status: "available",
  },
  {
    emoji: "👁️",
    title: "Lash Appointment",
    subtitle: "Fresh set, my treat",
    value: "1 Lash Set",
    description:
      "Your next lash appointment is paid for. Go get those gorgeous " +
      "lashes done and feel amazing.",
    code: "LASH-02",
    accent: "violet",
    status: "available",
  },
  {
    emoji: "💅",
    title: "Mani + Pedi",
    subtitle: "Whenever you fancy it",
    value: "Nails Set",
    description:
      "A full mani and pedi on me. Treat your hands and feet to a little " +
      "pampering session.",
    code: "NAILS-03",
    accent: "amber",
    status: "soon",
  },
  {
    emoji: "🍽️",
    title: "Date Night Dinner",
    subtitle: "Your choice of place",
    value: "Dinner for 2",
    description:
      "Pick the restaurant you've been wanting to try and let's go. " +
      "Dress up — it's a proper date.",
    code: "DATE-04",
    accent: "emerald",
    status: "soon",
  },
];
