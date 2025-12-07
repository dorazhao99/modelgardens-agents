// index.js
// -------------------------------------------------------------
// Note:
// This code was adapted from the repository:
//   https://github.com/raykuonz/slidev-mcp-server/tree/main
// Many thanks to the original author(s) for making this foundation available.
// -------------------------------------------------------------

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

// Slidev knowledge
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
      "Get Slidev guidance: best practices, themes, layouts, examples, and how to call build_complete_presentation. Essential for AI agents to understand Slidev best practices.",
    inputSchema: {
      presentationType: z
        .string()
        .optional()
        .describe(
          "Type of presentation. One of: 'technical', 'business', 'academic'. Please input EXACTLY one of these values (verbatim, no variations or abbreviations)."
        ),
    },
    outputSchema: {
      presentationTypeNormalized: z
        .string()
        .describe(
          "Normalized presentation type derived from the input: one of 'technical', 'business', or 'academic'."
        ),
      guidance: z.object({
        recommendedThemes: z.array(z.string()),
        structure: z.array(z.any()),
        tips: z.array(z.string()),
      }),
      overview: z.string(),
      themes: z.array(z.string()),
      layouts: z.array(z.string()),
      layoutUsage: z.record(z.string()),
      examples: z.record(z.any()),
      bestPractices: z.object({
        structure: z.array(z.string()),
        content: z.array(z.string()),
        technical: z.array(z.string()),
      }),
      buildTool: z.object({
        name: z.string(),
        // Use a flexible record here since we are returning descriptive strings for human guidance
        inputSchema: z.record(z.any()),
        notes: z.array(z.string()),
        sampleCall: z.string(),
      }),
      suggestedWorkflow: z.array(z.string()),
    },
  },
  async (input) => {
    function normalizePresentationType(raw) {
      const s = ((raw ?? "") + "").toLowerCase().trim();
      if (!s) return "technical";
      // Academic/research-oriented
      if (
        s.includes("academic") ||
        s.includes("research") ||
        s.includes("irb") ||
        s.includes("study") ||
        s.includes("thesis") ||
        s.includes("paper") ||
        s.includes("ethics")
      ) {
        return "academic";
      }
      // Business/executive-oriented
      if (
        s.includes("business") ||
        s.includes("exec") ||
        s.includes("stakeholder") ||
        s.includes("review") ||
        s.includes("planning") ||
        s.includes("roadmap") ||
        s.includes("sales")
      ) {
        return "business";
      }
      if (s.includes("technical") || s.includes("engineering") || s.includes("developer")) {
        return "technical";
      }
      return "technical";
    }

    const normalizedType = normalizePresentationType(input.presentationType);
    const guidance = generateSlidevGuidance(normalizedType);

    const layoutUsage = {
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
    };

    const buildTool = {
      name: "build_complete_presentation",
      inputSchema: {
        name: "string (file name without extension)",
        title: "string (presentation title)",
        slides:
          "array of slides: [{ layout?: string, title?: string, content?: string, code?: string, codeLanguage?: string }]. The first slide defaults to layout 'cover' if missing; subsequent slides default to 'default'. Separate content with '\\n' as needed.",
        theme:
          "optional string or null (e.g., 'default', 'vitesse', 'carbon', 'seriph'). If omitted or null, Slidev default applies. If frontmatter theme is present, it is used.",
        author: "optional string (author name)",
      },
      notes: [
        "Keep one main idea per slide; use 'section' to separate parts.",
        "If including code, set both 'code' and 'codeLanguage' (e.g., 'ts', 'py').",
        "Use explicit layouts when you care about composition; otherwise rely on sensible defaults.",
        "Themes can be plain names like 'seriph' which resolve to @slidev/theme-seriph in the export environment.",
      ],
      sampleCall: JSON.stringify(
        {
          name: "mcp_minimal_test",
          title: "MCP Minimal Test",
          author: "MCP Tester",
          theme: "seriph",
          slides: [
            {
              layout: "cover",
              title: "MCP + Slidev",
              content: "This is the cover slide.",
            },
            {
              layout: "default",
              title: "Second Slide",
              content: "- Bullet A\\n- Bullet B\\n- Bullet C",
            },
            {
              layout: "two-cols",
              title: "Code + Notes",
              content: "Left: explanation\\nRight: code example",
              code: "console.log('Hello Slidev');",
              codeLanguage: "js",
            },
          ],
        },
        null,
        2
      ),
    };

    const payload = {
      presentationTypeNormalized: normalizedType,
      guidance,
      overview: `${slidevKnowledge.overview.description} Visit ${slidevKnowledge.overview.website} for full documentation.`,
      themes: slidevKnowledge.themes,
      layouts: slidevKnowledge.layouts,
      layoutUsage,
      examples: slidevKnowledge.exampleStructures,
      bestPractices: slidevKnowledge.bestPractices,
      buildTool,
      suggestedWorkflow: [
        "1) Choose presentation type (technical/business/academic) and theme.",
        "2) Draft outline using layouts: cover → section → default/two-cols → image → end.",
        "3) Build slides with build_complete_presentation, providing explicit layouts for key slides.",
        "4) Export to PDF via export_to_pdf (optionally with withClicks, range, dark).",
      ],
    };

    return {
      content: [{ type: "text", text: JSON.stringify(payload, null, 2) }],
      structuredContent: payload,
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
      "Use get_slidev_guidance to choose themes, layouts, and structure first, then pass the finalized slides here. " +
      "This tool writes a single .md file in the configured presentations directory and is the primary way to create presentations programmatically.",
    inputSchema: {
      name: z.string().describe("Presentation file name (without extension)"),
      title: z.string().describe("Presentation title"),
      slides: z
        .array(
          z.object({
            layout: z.string().optional(),
            title: z.string().optional(),
            content: z.string().optional(),
            code: z.string().optional(),
            codeLanguage: z.string().optional(),
          })
        )
        .describe("Array of slide objects to create in order"),
      theme: z
        .string()
        .nullable()
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
      const payload = {
        message: "No slides provided. 'slides' array must contain at least one slide.",
        slideCount: 0,
        filePath: "",
        success: false,
      };
      return {
        content: [{ type: "text", text: JSON.stringify(payload, null, 2) }],
        structuredContent: payload,
      };
    }

    let markdown = "";

    // Build all slides
    input.slides.forEach((slide, index) => {
      if (index === 0) {
        // First slide: combine frontmatter/presentation metadata with layout
        let firstSlideHeader = "---\n";
        const firstLayout = slide.layout && slide.layout.trim().length > 0 ? slide.layout : "cover";
        firstSlideHeader += `layout: ${firstLayout}\n`;
        const themeValue =
          typeof input.theme === "string" && input.theme.trim().length > 0 ? input.theme : undefined;
        if (themeValue) firstSlideHeader += `theme: ${themeValue}\n`;
        firstSlideHeader += `title: "${input.title}"\n`;
        if (input.author) firstSlideHeader += `author: "${input.author}"\n`;
        firstSlideHeader += "---\n";

        markdown += firstSlideHeader;
      } else {
        const layout = slide.layout && slide.layout.trim().length > 0 ? slide.layout : "default";
        markdown += `\n---\nlayout: ${layout}\n---\n`;
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

    const payload = {
      message: `Complete presentation '${input.title}' with ${input.slides.length} slides created and saved successfully!`,
      slideCount: input.slides.length,
      filePath,
      success: true,
    };
    return {
      content: [{ type: "text", text: JSON.stringify(payload, null, 2) }],
      structuredContent: payload,
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
      "Export a Slidev presentation to PDF using Slidev's export pipeline. Prefer providing 'inputPath' (absolute .md) and 'outputPath'. If omitted, the tool falls back to sensible defaults.",
    inputSchema: {
      inputPath: z
        .string()
        .optional()
        .nullable()
        .describe("Absolute path to the Slidev markdown file to export (e.g., '/abs/path/to/deck.md'). If omitted, 'name' is used to resolve the path under SLIDEV_DIR. NOTE: THE PATH MUST BE ABSOLUTE, NOT RELATIVE."),
      name: z
        .string()
        .optional()
        .nullable()
        .describe(
          "Presentation name to export (without extension). Used only when 'inputPath' is not provided. Defaults to the last built presentation name."
        ),
      outputPath: z
        .string()
        .optional()
        .nullable()
        .describe(
          "Output PDF file path. Defaults: if inputPath provided, '<dirname(inputPath)>/<basename>.pdf'; otherwise 'presentations/pdfs/[name].pdf' under SLIDEV_DIR or fallback."
        ),
      withClicks: z
        .boolean()
        .nullable()
        .optional()
        .describe("Export with click animations as separate pages (default false)"),
      range: z
        .string()
        .nullable()
        .optional()
        .describe("Export specific slides (e.g., '1,3-5,8')"),
      dark: z
        .boolean()
        .nullable()
        .optional()
        .describe("Export using dark theme (default false)"),
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
      // Resolve markdown input
      let mdPath = null;
      if (input.inputPath && String(input.inputPath).trim().length > 0) {
        const p = String(input.inputPath);
        mdPath = p;
        if (!existsSync(mdPath)) {
          throw new Error(`Input markdown not found: ${mdPath}`);
        }
      } else {
        const name = input.name || presentationName;
        if (!name) {
          throw new Error(
            "No inputPath provided and no presentation name available. Provide 'inputPath' or 'name' (after building a presentation)."
          );
        }
        const presentationsDir =
          process.env.SLIDEV_DIR && process.env.SLIDEV_DIR.length > 0
            ? process.env.SLIDEV_DIR
            : getDefaultSlidevDir();
        const candidate = join(presentationsDir, `${name}.md`);
        if (!existsSync(candidate)) {
          throw new Error(`Presentation file not found: ${candidate}`);
        }
        mdPath = candidate;
      }

      // Ensure output directory exists (pdfs sub-folder)
      let outputPath = input.outputPath;
      if (!outputPath || String(outputPath).trim().length === 0) {
        // Default output near input when inputPath is provided; otherwise default to SLIDEV_DIR/pdfs
        const pathModule = await import("path");
        const inputDir = pathModule.dirname(mdPath);
        const baseName = pathModule.basename(mdPath).replace(/\.md$/i, "");
        outputPath = pathModule.join(inputDir, `${baseName}.pdf`);
      } else {
        // Ensure the parent directory exists
        const pathModule = await import("path");
        const outDir = pathModule.dirname(outputPath);
        if (!existsSync(outDir)) {
          mkdirSync(outDir, { recursive: true });
        }
      }

      // Use existing export wrapper
      const { default: exportToPDF } = await import("../export-wrapper.js");

      const exportOptions = {
        withClicks: input.withClicks === true,
        range:
          typeof input.range === "string" && input.range.trim().length > 0
            ? input.range
            : null,
        dark: input.dark === true,
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

      const payload = {
        message: `PDF exported successfully! File saved at: ${pdfPath}`,
        pdfPath,
        slideCount,
        success: true,
      };
      return {
        content: [{ type: "text", text: JSON.stringify(payload, null, 2) }],
        structuredContent: payload,
      };
    } catch (error) {
      const message = error?.message || String(error);

      if (message.toLowerCase().includes("playwright")) {
        const payload = {
          message:
            "PDF export failed: Playwright dependency issue. Run: npm install -D playwright-chromium",
          pdfPath: "",
          slideCount: 0,
          success: false,
        };
        return {
          content: [{ type: "text", text: JSON.stringify(payload, null, 2) }],
          structuredContent: payload,
        };
      }

      if (message.includes("ENOENT") || message.includes("command not found")) {
        const payload = {
          message:
            "PDF export failed: Slidev CLI not found. Run: npm install -g @slidev/cli (or add it to your project devDependencies).",
          pdfPath: "",
          slideCount: 0,
          success: false,
        };
        return {
          content: [{ type: "text", text: JSON.stringify(payload, null, 2) }],
          structuredContent: payload,
        };
      }

      const payload = {
        message: `PDF export failed: ${message}`,
        pdfPath: "",
        slideCount: 0,
        success: false,
      };
      return {
        content: [{ type: "text", text: JSON.stringify(payload, null, 2) }],
        structuredContent: payload,
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
console.error("📚 Guidance tool:");
console.error("- get_slidev_guidance: Consolidated guidance (themes, layouts, examples, build tool usage)");
console.error("🛠 Main creation/export tools:");
console.error("- build_complete_presentation: Create & save full presentation in one call");
console.error("- export_to_pdf: Export an existing presentation to PDF");
console.error("Documentation: https://sli.dev/guide/");
console.error("Ready to accept MCP connections via stdio...");