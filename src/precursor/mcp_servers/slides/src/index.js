// -------------------------------------------------------------
// Note:
// This code was adapted from the repository:
//   https://github.com/raykuonz/slidev-mcp-server/tree/main
// Many thanks to the original author(s) for making this foundation available.
// -------------------------------------------------------------

// slidev-mcp.ts

// Core MCP + transport
import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";

// Schemas & utilities
import { z } from "zod";
import {
  writeFileSync,
  readFileSync,
  mkdirSync,
  existsSync,
} from "fs";
import { join } from "path";
import { homedir } from "os";

// Slidev knowledge (unchanged)
import { slidevKnowledge, generateSlidevGuidance } from "./slidev-knowledge.js";

// Keep only minimal shared state: current presentation name
let presentationName = "";

// Create MCP server
const server = new McpServer({
  name: "slidev-mcp",
  version: "1.0.0",
});

/* -------------------------------------------------------------------------- */
/*                              GUIDANCE TOOLS                                */
/* -------------------------------------------------------------------------- */

server.registerTool(
  "get_slidev_guidance",
  {
    description:
      "Get Slidev-specific guidance and recommendations for creating presentations. Essential for AI agents to understand Slidev best practices.",
    inputSchema: {
      presentationType: z
        .string()
        .optional()
        .describe("Type of presentation: 'technical', 'business', or 'academic'"),
    },
    outputSchema: {
      guidance: z.object({
        recommendedThemes: z.array(z.string()),
        structure: z.array(z.any()),
        tips: z.array(z.string()),
      }),
      overview: z.string(),
    },
  },
  async (input) => {
    const type = input.presentationType || "technical";
    const guidance = generateSlidevGuidance(type);

    return {
      structuredContent: {
        guidance,
        overview: `${slidevKnowledge.overview.description} Visit ${slidevKnowledge.overview.website} for full documentation.`,
      },
    };
  }
);

server.registerTool(
  "list_slidev_themes",
  {
    description:
      "Get list of available Slidev themes with recommendations for different presentation types.",
    inputSchema: {},
    outputSchema: {
      allThemes: z.array(z.string()),
      businessThemes: z.array(z.string()),
      technicalThemes: z.array(z.string()),
      recommendation: z.string(),
    },
  },
  async () => {
    return {
      structuredContent: {
        allThemes: slidevKnowledge.themes,
        businessThemes: ["apple-basic", "minimal", "seriph", "academic", "border"],
        technicalThemes: ["default", "vitesse", "carbon", "dracula", "geist"],
        recommendation:
          "Choose themes based on audience: business presentations should use clean, professional themes while technical presentations can use developer-focused themes.",
      },
    };
  }
);

server.registerTool(
  "get_slidev_layout_guide",
  {
    description:
      "Get guidance on Slidev layouts and when to use each layout type for optimal presentation structure.",
    inputSchema: {},
    outputSchema: {
      layouts: z.array(z.string()),
      usage: z.record(z.string()),
      examples: z.record(z.any()),
    },
  },
  async () => {
    return {
      structuredContent: {
        layouts: slidevKnowledge.layouts,
        usage: {
          cover: "Use for title slides - includes title, subtitle, author",
          intro: "Use for introduction slides with key points",
          section: "Use to separate major sections of presentation",
          "two-cols": "Use for side-by-side content like code + explanation",
          image: "Use for full-screen images with overlay text",
          "image-left": "Use for content with supporting images (image on the left)",
          "image-right": "Use for content with supporting images (image on the right)",
          quote: "Use for testimonials, quotes, or key statements",
          fact: "Use for statistics and important numbers",
          statement: "Use for bold statements or value propositions",
          end: "Use for conclusion, thank you, and Q&A slides",
        },
        examples: slidevKnowledge.exampleStructures,
      },
    };
  }
);

/* -------------------------------------------------------------------------- */
/*                 MAIN PRESENTATION CREATION (ATOMIC BUILD)                  */
/* -------------------------------------------------------------------------- */

function getUserDataDir() {
  const home = homedir();
  const platform = process.platform;
  if (platform === "win32") {
    return process.env.LOCALAPPDATA || process.env.APPDATA || join(home, "AppData", "Local");
  }
  if (platform === "darwin") {
    return join(home, "Library", "Application Support");
  }
  return join(home, ".local", "share");
}

function getDefaultSlidevDir() {
  return join(getUserDataDir(), "precursor", "slides");
}

server.registerTool(
  "build_complete_presentation",
  {
    description:
      "Build a complete Slidev presentation with multiple slides in one call. " +
      "Agents should typically use get_slidev_guidance, list_slidev_themes, and get_slidev_layout_guide " +
      "to choose themes, layouts, and structure first, then pass the finalized slides here. " +
      "This tool writes a single .md file in the configured presentations directory and is the primary way to create presentations programmatically.",
    inputSchema: {
      name: z.string().describe("Presentation file name (without extension)"),
      title: z.string().describe("Presentation title"),
      slides: z
        .array(
          z.object({
            layout: z.string(),
            title: z.string().optional(),
            content: z.string().optional(),
            code: z.string().optional(),
            codeLanguage: z.string().optional(),
          })
        )
        .describe("Array of slide objects to create in order"),
      theme: z
        .string()
        .optional()
        .describe("Slidev theme (e.g., apple-basic, minimal, seriph, default, vitesse, carbon)"),
      author: z.string().optional().describe("Author name"),
    },
    outputSchema: {
      message: z.string(),
      slideCount: z.number(),
      filePath: z.string(),
      success: z.boolean(),
    },
  },
  async (input) => {
    // Track the "current" presentation name for export_to_pdf's default
    presentationName = input.name;

    if (!input.slides || input.slides.length === 0) {
      return {
        structuredContent: {
          message: "No slides provided. 'slides' array must contain at least one slide.",
          slideCount: 0,
          filePath: "",
          success: false,
        },
      };
    }

    let markdown = "";

    // Build all slides
    input.slides.forEach((slide, index) => {
      if (index === 0) {
        // First slide: combine frontmatter/presentation metadata with layout
        let firstSlideHeader = "---\n";
        firstSlideHeader += `layout: ${slide.layout}\n`;
        if (input.theme) firstSlideHeader += `theme: ${input.theme}\n`;
        firstSlideHeader += `title: "${input.title}"\n`;
        if (input.author) firstSlideHeader += `author: "${input.author}"\n`;
        firstSlideHeader += "---\n";

        markdown += firstSlideHeader;
      } else {
        markdown += `\n---\nlayout: ${slide.layout}\n---\n`;
      }

      if (slide.title) {
        markdown += `\n# ${slide.title}\n`;
      }

      if (slide.content) {
        markdown += `\n${slide.content}\n`;
      }

      if (slide.code && slide.codeLanguage) {
        markdown += `\n\`\`\`${slide.codeLanguage}\n${slide.code}\n\`\`\`\n`;
      }
    });

    // Determine directory from environment variable or fallback
    const presentationsDir =
      process.env.SLIDEV_DIR && process.env.SLIDEV_DIR.length > 0
        ? process.env.SLIDEV_DIR
        : getDefaultSlidevDir();

    if (!existsSync(presentationsDir)) {
      mkdirSync(presentationsDir, { recursive: true });
    }

    const filePath = join(presentationsDir, `${presentationName}.md`);
    writeFileSync(filePath, markdown, "utf8");

    console.error(`📁 Saved presentation to: ${filePath}`);

    return {
      structuredContent: {
        message: `Complete presentation '${input.title}' with ${input.slides.length} slides created and saved successfully!`,
        slideCount: input.slides.length,
        filePath,
        success: true,
      },
    };
  }
);

/* -------------------------------------------------------------------------- */
/*                              PDF EXPORT TOOL                               */
/* -------------------------------------------------------------------------- */

server.registerTool(
  "export_to_pdf",
  {
    description:
      "Export a Slidev presentation to PDF using Slidev's export pipeline. Requires playwright-chromium to be installed.",
    inputSchema: {
      name: z
        .string()
        .optional()
        .describe(
          "Presentation name to export (without extension). Defaults to the last built presentation name."
        ),
      outputPath: z
        .string()
        .optional()
        .describe(
          "Output PDF file path (default: in presentations/pdfs/[name].pdf under SLIDEV_DIR or fallback)"
        ),
      withClicks: z
        .boolean()
        .optional()
        .describe("Export with click animations as separate pages"),
      range: z
        .string()
        .optional()
        .describe("Export specific slides (e.g., '1,3-5,8')"),
      dark: z
        .boolean()
        .optional()
        .describe("Export using dark theme"),
    },
    outputSchema: {
      message: z.string(),
      pdfPath: z.string(),
      slideCount: z.number(),
      success: z.boolean(),
    },
  },
  async (input) => {
    try {
      const name = input.name || presentationName;
      if (!name) {
        throw new Error(
          "No presentation name provided and no current presentation. Provide 'name' or build a presentation first."
        );
      }

      const presentationsDir =
        process.env.SLIDEV_DIR && process.env.SLIDEV_DIR.length > 0
          ? process.env.SLIDEV_DIR
          : getDefaultSlidevDir();
      const mdPath = join(presentationsDir, `${name}.md`);

      if (!existsSync(mdPath)) {
        throw new Error(`Presentation file not found: ${mdPath}`);
      }

      // Ensure output directory exists (pdfs sub-folder)
      const pdfDir = join(presentationsDir, "pdfs");
      if (!existsSync(pdfDir)) {
        mkdirSync(pdfDir, { recursive: true });
      }

      const outputPath =
        input.outputPath || join(pdfDir, `${name}.pdf`);

      // Use existing export wrapper
      const { default: exportToPDF } = await import("../export-wrapper.js");

      const exportOptions = {
        withClicks: input.withClicks ?? false,
        range: input.range ?? null,
        dark: input.dark ?? false,
      };

      console.error("🚀 Starting PDF export via export-wrapper...");
      const result = await exportToPDF(mdPath, outputPath, exportOptions);

      if (!result.success) {
        throw new Error(result.message);
      }

      const pdfPath = result.pdfPath || outputPath;

      // Count slides by reading the markdown file
      const markdown = readFileSync(mdPath, "utf8");
      const slideMatches = markdown.match(/---\nlayout:/g) || [];
      const slideCount = slideMatches.length || 1;

      return {
        structuredContent: {
          message: `PDF exported successfully! File saved at: ${pdfPath}`,
          pdfPath,
          slideCount,
          success: true,
        },
      };
    } catch (error) {
      const message = error?.message || String(error);

      if (message.toLowerCase().includes("playwright")) {
        return {
          structuredContent: {
            message:
              "PDF export failed: Playwright dependency issue. Run: npm install -D playwright-chromium",
            pdfPath: "",
            slideCount: 0,
            success: false,
          },
        };
      }

      if (message.includes("ENOENT") || message.includes("command not found")) {
        return {
          structuredContent: {
            message:
              "PDF export failed: Slidev CLI not found. Run: npm install -g @slidev/cli (or add it to your project devDependencies).",
            pdfPath: "",
            slideCount: 0,
            success: false,
          },
        };
      }

      return {
        structuredContent: {
          message: `PDF export failed: ${message}`,
          pdfPath: "",
          slideCount: 0,
          success: false,
        },
      };
    }
  }
);

/* -------------------------------------------------------------------------- */
/*                           SERVER BOOTSTRAP / I/O                           */
/* -------------------------------------------------------------------------- */

const transport = new StdioServerTransport();
server.connect(transport);

// Ensure default presentations directory exists at startup
const defaultDir =
  process.env.SLIDEV_DIR && process.env.SLIDEV_DIR.length > 0
    ? process.env.SLIDEV_DIR
    : getDefaultSlidevDir();

if (!existsSync(defaultDir)) {
  mkdirSync(defaultDir, { recursive: true });
  console.error(`Created presentations directory at: ${defaultDir}`);
}

console.error("Slidev MCP STDIO server started with the following tools:");
console.error("📚 Guidance tools:");
console.error("- get_slidev_guidance: Slidev best practices and recommendations");
console.error("- list_slidev_themes: Available themes + recommendations");
console.error("- get_slidev_layout_guide: Layout guidance and examples");
console.error("🛠 Main creation/export tools:");
console.error("- build_complete_presentation: Create & save full presentation in one call");
console.error("- export_to_pdf: Export an existing presentation to PDF");
console.error("Documentation: https://sli.dev/guide/");
console.error("Ready to accept MCP connections via stdio...");