export const faqGroups: { title: string; items: { q: string; a: string }[] }[] = [
  {
    title: "The product",
    items: [
      {
        q: "What is ContentFactory?",
        a: "An AI marketing agent for small businesses. You describe your business once; it plans your content, writes posts, suggests visuals, schedules and publishes them after your approval, and learns from the results.",
      },
      {
        q: "Who is it for?",
        a: "Owners and small teams at cafés, restaurants, salons, shops, studios, clinics, local services and online stores, plus freelancers and agencies who manage several businesses.",
      },
      {
        q: "Does ContentFactory train an AI model on my data?",
        a: "No. It keeps a structured memory of your business and your results, and gives the relevant parts to the AI for each task. Nothing is used to train or fine-tune models, and you can review or delete what it remembers.",
      },
      {
        q: "Which platforms can it publish to?",
        a: "Instagram, Facebook, TikTok and YouTube, through each platform's official API. LinkedIn, Pinterest and X are planned.",
      },
    ],
  },
  {
    title: "Control and safety",
    items: [
      {
        q: "Will anything be posted without my approval?",
        a: "No, not by default. Every post waits for approval, and an unapproved post is never published. On Business and Agency you can turn approval off yourself.",
      },
      {
        q: "What is checked before a post publishes?",
        a: "That it's approved (unless you've turned approval off on Business or Agency), that the account is connected, that the format suits the platform, that captions and hashtags fit its limits, and that the media is valid. Drafts that use words or topics you've blocked are flagged when they're written.",
      },
      {
        q: "Are the analytics real?",
        a: "Yes. Numbers come from each platform's API. If a platform doesn't provide a metric, you'll see \"Not available from this platform\" rather than an estimate.",
      },
    ],
  },
  {
    title: "Plans and billing",
    items: [
      {
        q: "Is there a free plan?",
        a: "Yes. The Free plan includes 1 business, 1 social account, 10 AI content generations, 10 images and 2 video credits a month. No card is required.",
      },
      {
        q: "Is anything unlimited?",
        a: "No. AI work costs real money to run, so every plan has clear monthly quotas. You always see how much you've used.",
      },
      {
        q: "What happens when I reach a limit?",
        a: "AI generation pauses until your quota resets or you upgrade. Scheduled posts that are already approved still publish.",
      },
      {
        q: "How does billing work?",
        a: "Payments are handled by Paddle, which acts as merchant of record and takes care of sales tax and VAT. You can upgrade, downgrade or cancel from Billing settings at any time.",
      },
      {
        q: "What happens to my content if I cancel?",
        a: "Your workspace moves to the Free plan at the end of the billing period. Your content, media and memory stay, within Free plan limits.",
      },
    ],
  },
];
