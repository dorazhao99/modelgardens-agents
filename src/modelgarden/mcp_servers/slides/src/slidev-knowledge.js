// slidev-knowledge.js
// Slidev Knowledge Base for AI Agents
// Based on https://sli.dev/guide/

export const slidevKnowledge = {
  overview: {
    description:
      "Slidev is a web-based slides maker designed for developers. It uses Markdown with Vue.js components for pixel-perfect, interactive presentations.",
    website: "https://sli.dev/guide/",
    syntax: "Markdown with frontmatter configuration and special directives",
  },

  themes: [
    "default",
    "apple-basic",
    "bricks",
    "brutalist",
    "academic",
    "border",
    "carbon",
    "chalkboard",
    "cover",
    "dracula",
    "eloc",
    "geist",
    "glass",
    "landing",
    "light-icons",
    "materia",
    "minimal",
    "none",
    "orange",
    "penguin",
    "purplin",
    "seriph",
    "shibainu",
    "simple",
    "sky",
    "space",
    "teeth",
    "theme-academic",
    "unicorn",
    "vitesse",
    "waves",
  ],

  frontmatterOptions: {
    theme: "Theme name (e.g., 'default', 'apple-basic')",
    background: "Background image or color",
    title: "Presentation title",
    info: "Presentation description",
    author: "Author name",
    keywords: "Comma-separated keywords",
    transition: "Slide transition effect",
    layout: "Default layout for slides",
    highlighter: "Code highlighter (prism, shiki)",
    lineNumbers: "Show line numbers in code blocks",
    monaco: "Enable Monaco editor features",
    download: "Enable download button",
    exportFilename: "Filename for exports",
    colorSchema: "Color scheme (auto, light, dark)",
    routerMode: "Router mode (history, hash)",
    aspectRatio: "Slide aspect ratio (16/9, 4/3)",
    canvasWidth: "Canvas width in pixels",
    favicon: "Custom favicon URL",
    plantUmlServer: "PlantUML server URL",
    fonts: "Custom fonts configuration",
  },

  layouts: [
    "center",
    "cover",
    "default",
    "end",
    "fact",
    "full",
    "image",
    "image-left",
    "image-right",
    "intro",
    "none",
    "quote",
    "section",
    "statement",
    "two-cols",
    "two-cols-header",
    "iframe",
    "iframe-left",
    "iframe-right",
  ],

  markdownFeatures: {
    slides: "Use '---' to separate slides",
    headings: "# ## ### for different heading levels",
    lists: "- or * for bullet points, 1. for numbered lists",
    codeBlocks: "```language for syntax highlighting",
    images: "![alt](url) or <img> tags with styling",
    links: "[text](url) for hyperlinks",
    emphasis: "*italic* **bold** for text formatting",
    blockquotes: "> for quotations",
    tables: "| header | format | for tables",
  },

  slidevSpecificFeatures: {
    layouts: "Use 'layout: layoutname' in slide frontmatter",
    components: "Vue components available: <Tweet>, <Youtube>, <CodeRunner>, etc.",
    animations: "Use v-motion for animations",
    clicks: "Use v-click for step-by-step reveals",
    math: "KaTeX support with $$ for math expressions",
    mermaid: "```mermaid for diagrams",
    monaco: "```ts {monaco} for live code editing",
    plantUml: "@startuml/@enduml for UML diagrams",
    windicss: "Utility CSS classes available",
    notes: "<!-- notes --> for presenter notes",
  },

  bestPractices: {
    structure: [
      "Start with title slide using 'cover' or 'intro' layout",
      "Use section slides to organize content",
      "Keep slides focused - one main idea per slide",
      "End with summary or 'end' layout slide",
    ],
    content: [
      "Use bullet points for readability",
      "Include code examples with proper syntax highlighting",
      "Use images and diagrams to support concepts",
      "Keep text concise and scannable",
    ],
    technical: [
      "Choose appropriate theme for audience",
      "Use consistent heading levels",
      "Include presenter notes for context",
      "Test exported versions before presenting",
    ],
  },

  exampleStructures: {
    technical: {
      slides: [
        { layout: "cover", content: "Title, subtitle, author" },
        { layout: "default", content: "Agenda/Overview" },
        { layout: "section", content: "Main topic sections" },
        { layout: "two-cols", content: "Code examples with explanations" },
        { layout: "image", content: "Diagrams and visuals" },
        { layout: "end", content: "Thank you and Q&A" },
      ],
    },
    business: {
      slides: [
        { layout: "cover", content: "Professional title slide" },
        { layout: "fact", content: "Key statistics or problems" },
        { layout: "statement", content: "Solution or value proposition" },
        { layout: "image-right", content: "Features with visuals" },
        { layout: "quote", content: "Testimonials or quotes" },
        { layout: "end", content: "Call to action" },
      ],
    },
  },

  commonErrors: [
    "Missing '---' between slides",
    "Incorrect frontmatter syntax (must be at top)",
    "Using unsupported theme names",
    "Missing language in code blocks",
    "Inconsistent heading levels",
    "Too much text per slide",
  ],
};

export const generateSlidevGuidance = (presentationType = "technical") => {
  const structure =
    slidevKnowledge.exampleStructures[presentationType] ||
    slidevKnowledge.exampleStructures.technical;

  return {
    recommendedThemes:
      presentationType === "business"
        ? ["apple-basic", "minimal", "seriph", "academic"]
        : ["default", "vitesse", "carbon", "dracula"],

    structure: structure.slides,

    tips: [
      "Use frontmatter to configure theme and settings",
      "Separate slides with '---'",
      "Choose layouts that match your content type",
      "Include syntax highlighting for code",
      "Keep slides visually consistent",
      "When using two column structure use the format `Left: [left side content]\\nRight: [right side content]` so the parser formats the document correctly"
    ],
  };
};