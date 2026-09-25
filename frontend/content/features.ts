export interface FeatureSection {
  title: string;
  body: string;
  points?: string[];
}

export interface FeaturePageContent {
  slug: string;
  navLabel: string;
  h1: string;
  metaTitle: string;
  metaDescription: string;
  intro: string;
  sections: FeatureSection[];
  faq: { q: string; a: string }[];
  related: string[];
}

export const featurePages: FeaturePageContent[] = [
  {
    slug: "ai-marketing-agent",
    navLabel: "AI marketing agent",
    h1: "An AI marketing agent that works like a member of your team",
    metaTitle: "AI Marketing Agent for Small Businesses",
    metaDescription:
      "ContentFactory's AI marketing agent plans your content strategy, writes posts, schedules them, and learns from real results. Built for small businesses.",
    intro:
      "Most AI tools wait for you to type a prompt. ContentFactory's agent starts from your business: what you sell, who buys it, how you talk, and what has worked before. It proposes the week's plan, drafts the posts, and brings them to you for approval.",
    sections: [
      {
        title: "It starts from your business, not a blank box",
        body: "During onboarding you describe your products, customers, locations, goals and tone. That profile, plus everything the agent learns later, is loaded into every task, so you never re-explain your business.",
        points: [
          "Brand voice, words to use and words to avoid",
          "Products with prices, benefits and photos",
          "Goals such as more visits, bookings or online orders",
          "Topics and claims you never want published",
        ],
      },
      {
        title: "Specialist agents, one record of what they did",
        body: "Content, Creative, Publishing and Analytics agents each handle one part of the job. The activity timeline shows each step in plain language: what ran, what it chose and what it cost. Strategy and Research agents that plan on their own are coming soon",
      },
      {
        title: "Limits you can see",
        body: "Every agent run has a maximum number of steps, a time limit, a cost ceiling and a retry limit. If a run hits a limit it stops and tells you, instead of looping in the background. AI work counts against your plan's monthly quota, which is always shown in your workspace.",
      },
      {
        title: "Memory, not model training",
        body: "ContentFactory doesn't retrain an AI model on your data. It stores structured facts about your business and your results: which topics earn saves, which hooks hold attention, which times get reach. The agent retrieves the relevant facts for each task. You can review, edit or delete anything it remembers.",
      },
    ],
    faq: [
      {
        q: "Will the agent post without asking me?",
        a: "Not unless you turn approval off, which is available on Business and Agency plans. By default every post waits for your approval, and nothing publishes if you don't approve it.",
      },
      {
        q: "Does it use my data to train AI models?",
        a: "No. Your business information is stored in your workspace and used as context for your own tasks. It is not used to train or fine-tune models.",
      },
      {
        q: "What if the agent gets something wrong about my business?",
        a: "Open Marketing Memory and correct or delete the fact. Corrections take effect on the next task.",
      },
    ],
    related: ["content-creation", "social-media-automation", "analytics"],
  },
  {
    slug: "content-creation",
    navLabel: "Content creation",
    h1: "AI content creation in your own brand voice",
    metaTitle: "AI Content Creation for Social Media",
    metaDescription:
      "Generate hooks, captions, carousels, Reels scripts and CTAs that sound like your business. ContentFactory uses your photos first and creates visuals only when needed.",
    intro:
      "ContentFactory writes complete posts for the platform they're going to: the hook, the caption, the call to action, hashtags where they help, and a visual plan. Drafts come with variations so you can choose, and the agent learns from what you edit.",
    sections: [
      {
        title: "Formats for each platform",
        body: "A post for Instagram is not a post for LinkedIn. Each draft is shaped for its destination.",
        points: [
          "Single-image posts and carousels with slide-by-slide copy",
          "Reels, TikTok and YouTube Shorts scripts with scene plans",
          "Stories with frame-by-frame text",
          "Longer captions for Facebook and LinkedIn",
        ],
      },
      {
        title: "Your photos first",
        body: "Upload photos and videos of your products, space and team. Add tags and descriptions, or let the agent suggest them. When writing a post, it looks through your library first. Your preference decides how strongly: always use my media, use it when relevant, or never.",
      },
      {
        title: "Edits teach it your taste",
        body: "When you shorten a caption, swap a word, or reject a draft, that's a signal. Repeated corrections become style notes in your brand memory, so the next drafts need fewer changes.",
      },
    ],
    faq: [
      {
        q: "How many posts can I generate?",
        a: "Each plan has a monthly allowance: 10 AI content generations on Free, 60 on Starter, 250 on Business and 700 on Agency. The count is shown in your workspace and resets monthly.",
      },
      {
        q: "Can I write my own posts too?",
        a: "Yes. You can write from scratch, paste existing copy, or ask the agent to improve something you wrote.",
      },
      {
        q: "Which languages are supported?",
        a: "Posts can be written in the language you choose for your business profile. Quality is best in widely spoken languages; review drafts carefully in less common ones.",
      },
    ],
    related: ["ai-images", "ai-video", "ai-marketing-agent"],
  },
  {
    slug: "social-media-automation",
    navLabel: "Social media automation",
    h1: "Social media automation with approvals built in",
    metaTitle: "Social Media Automation and Scheduling",
    metaDescription:
      "Plan a content calendar, approve posts in one click, and publish to Instagram, Facebook, TikTok and YouTube on schedule. Reminders before every post.",
    intro:
      "The content calendar shows everything planned, waiting for approval, scheduled and published. Approve from the dashboard or from a reminder, and ContentFactory publishes at the planned time through each platform's official API.",
    sections: [
      {
        title: "A calendar you can rearrange",
        body: "Switch between month, week and list views. Drag a post to another day, change its platform, duplicate it, or pause it. Filters show only what needs your attention.",
      },
      {
        title: "Reminders before anything goes out",
        body: "Choose when you're reminded about posts that need approval: 24 hours before, 6 hours, 1 hour, or not at all. Each reminder shows the post and lets you approve, edit, regenerate or reject it.",
      },
      {
        title: "Publishing you can trust",
        body: "Every scheduled post is published exactly once. If a platform is temporarily unavailable, ContentFactory retries with increasing delays. If a connection expires, you're asked to reconnect, and the post is never marked as published unless the platform confirms it.",
        points: [
          "Instagram and Facebook through Meta's official APIs",
          "TikTok and YouTube through their official APIs",
          "LinkedIn, Pinterest and X support is planned",
        ],
      },
    ],
    faq: [
      {
        q: "Do I need a business account on Instagram?",
        a: "Yes. Instagram only allows publishing through its API for professional (business or creator) accounts connected to a Facebook Page.",
      },
      {
        q: "What happens if publishing fails?",
        a: "The post is marked as failed with the reason, you get a notification, and you can retry once the cause is fixed. Posts are never silently dropped.",
      },
      {
        q: "Can I turn on full automation?",
        a: "On Business and Agency plans you can turn approval off, so posts publish at their scheduled time without waiting for you. Every post is still checked against the platform's rules first. An agent that plans and schedules a week on its own is coming soon",
      },
    ],
    related: ["ai-marketing-agent", "content-creation", "analytics"],
  },
  {
    slug: "analytics",
    navLabel: "Analytics",
    h1: "Social media analytics that tell you what to do next",
    metaTitle: "Social Media Analytics and Marketing Insights",
    metaDescription:
      "See reach, views, engagement, saves, shares and watch time from your connected platforms, with insights that always show sample size and time period.",
    intro:
      "ContentFactory collects performance data from each connected platform and turns it into plain-language insights. Every insight shows how many posts it's based on and over what period, so you know how much to trust it.",
    sections: [
      {
        title: "Only real numbers",
        body: "Metrics come from the platforms' own APIs. When a platform doesn't provide a metric for a post type, the report shows \"Not available from this platform\" instead of an estimate.",
        points: [
          "Reach, impressions and views",
          "Likes, comments, saves and shares",
          "Profile visits, link clicks and follower growth",
          "Watch time and completion rate for video",
        ],
      },
      {
        title: "Insights with evidence",
        body: "The Analytics agent compares groups of posts: educational against promotional, morning against evening, one hook style against another. It only states a conclusion when there are enough posts in each group, and it always shows the sample size and date range.",
      },
      {
        title: "Experiments, not hunches",
        body: "On paid plans you can test one thing at a time, such as two hooks or two posting times, and let the results decide. Finished experiments are saved to your Marketing Memory.",
      },
    ],
    faq: [
      {
        q: "How often are metrics updated?",
        a: "Recent posts are checked several times in their first days, when numbers change fastest, and less often after that. Each platform has its own update schedule and rate limits.",
      },
      {
        q: "Why is a metric missing for some posts?",
        a: "Some platforms don't report every metric for every post type or account type. ContentFactory shows that it's unavailable rather than guessing.",
      },
      {
        q: "Can I export my data?",
        a: "Your data remains yours. You can export it, or delete your workspace, at any time.",
      },
    ],
    related: ["ai-marketing-agent", "social-media-automation", "content-creation"],
  },
  {
    slug: "ai-images",
    navLabel: "AI images",
    h1: "AI image generation that fits your brand",
    metaTitle: "AI Image Generation for Marketing",
    metaDescription:
      "Create brand-aware marketing images for social posts: product scenes, promotions, seasonal posts and carousel covers, saved to your media library.",
    intro:
      "When your library doesn't have the right photo, ContentFactory can generate one. It writes the prompt from your brand colours, style and the post itself, then saves the result to your media library with its prompt and settings.",
    sections: [
      {
        title: "Built from your brand",
        body: "Image prompts include your brand colours and visual style. Start from the visual idea your agent wrote for a post, or describe the image yourself.",
        points: [
          "Product scenes and lifestyle images",
          "Promotional and seasonal posts",
          "Carousel covers and slide backgrounds",
          "Square, portrait, landscape and story shapes",
        ],
      },
      {
        title: "Never paid for twice",
        body: "Each generated image is stored with a fingerprint of its prompt and settings. If the same image is requested again, ContentFactory reuses the one in your library instead of generating and charging again.",
      },
      {
        title: "Clear limits",
        body: "Image generation counts against your plan's monthly image allowance: 10 on Free, 40 on Starter, 150 on Business and 400 on Agency. You see what's left before you generate.",
      },
    ],
    faq: [
      {
        q: "Can I use generated images commercially?",
        a: "Generated images are yours to use in your marketing, subject to the terms of the underlying image model provider, which are linked in our Terms.",
      },
      {
        q: "Will it replace my real photos?",
        a: "No. By default the agent prefers your own media when it's relevant. You can set it to always use your media or never.",
      },
      {
        q: "Can I change a generated image?",
        a: "Generate again with a changed prompt. Editing tools such as cropping aren't built in yet.",
      },
    ],
    related: ["content-creation", "ai-video", "ai-marketing-agent"],
  },
  {
    slug: "ai-video",
    navLabel: "AI video",
    h1: "Short videos from your own photos and clips",
    metaTitle: "Reels, TikToks and Shorts from Your Own Footage",
    metaDescription:
      "Turn your clips and photos into Reels, TikTok videos and YouTube Shorts: AI-written scripts and scene plans, then a video built from your own media with on-screen text.",
    intro:
      "Short video earns reach, but it takes time to plan and edit. ContentFactory writes the script and scene plan, then builds the video from your own clips and photos, with on-screen text, in the right shape for each platform.",
    sections: [
      {
        title: "Script first, then scenes",
        body: "Each video starts with a hook, a script and a scene-by-scene plan. You can edit the plan before anything is rendered, so credits aren't spent on a video you don't want.",
      },
      {
        title: "Your footage, edited for you",
        body: "Upload clips and photos from your phone. Pick one for each scene of the script, set how long it shows, and ContentFactory builds the video in vertical or square format.",
        points: ["Reels, TikTok and YouTube Shorts", "On-screen text for each scene", "Up to 20 scenes and 90 seconds", "Voiceovers and AI-generated scenes aren't available yet"],
      },
      {
        title: "Credits, not surprises",
        body: "Video uses credits: 2 a month on Free, 5 on Starter, 20 on Business and 50 on Agency. Each started 30 seconds costs one credit, and the cost is shown before you build.",
      },
    ],
    faq: [
      {
        q: "How long can videos be?",
        a: "Up to 90 seconds. Each started 30 seconds uses one video credit.",
      },
      {
        q: "Do I need to be on camera?",
        a: "No. Videos can be built from product photos, shots of your space and on-screen text.",
      },
      {
        q: "What if a build fails?",
        a: "Credits for failed builds are returned automatically.",
      },
    ],
    related: ["ai-images", "content-creation", "social-media-automation"],
  },
];

export function featureBySlug(slug: string): FeaturePageContent {
  const page = featurePages.find((p) => p.slug === slug);
  if (!page) throw new Error(`Unknown feature page ${slug}`);
  return page;
}
