# Optional MCP tools for architecture diagrams

MCP tools are optional. First check whether a relevant tool is already
available in the current Kiro session. Do not install packages or edit global
or workspace MCP configuration as part of diagram generation.

## Native Draw.io

The official Draw.io MCP tool server is `@drawio/mcp`. It accepts native
Draw.io XML and opens it in the Draw.io editor. Its tool set includes local
multi-page file operations (`list_pages`, `get_page`, and `set_page`) and
connector rerouting with `routing: "libavoid"`. This is the closest fit when
the deliverable must stay editable and use the Comprinno template. Use it to
inspect or adjust a disposable copy first; keep the repository's generated
file as the source of truth until the result is reviewed.

The server can also open a diagram from XML content in an editor URL. Treat that
as an interactive preview, not as proof that the local output file was saved.
The official server supports standard MCP clients; follow the current Draw.io
and Kiro configuration documentation if setup is explicitly requested.

## AWS architecture facts

If AWS Documentation MCP is available, use it to verify current service scope,
network behavior, or a disputed design choice. It is not needed for familiar,
stable facts. Keep the user in control of architecture choices that the docs
cannot determine (such as desired availability or cost tradeoffs).

## Alternative renderers

AWS's current Kiro guide recommends `diagrams-mcp` for natural-language
architecture generation and notes that the older `awslabs.aws-diagram-mcp-server`
package has been deprecated. `diagrams-mcp` uses the Python Diagrams library and
is useful for fast provider-icon drafts. Its output and layouts do not follow
the Comprinno Draw.io template, so do not substitute it for the editable
deliverable unless the user requests a different format or style.

References:

- [Draw.io MCP server](https://www.drawio.com/docs/manual/generate/drawio-mcp-server/)
- [Draw.io MCP tool server tools](https://github.com/jgraph/drawio-mcp/tree/main/mcp-tool-server)
- [Kiro MCP configuration](https://kiro.dev/docs/cli/mcp/)
- [AWS Kiro and MCP diagram guide](https://aws.amazon.com/blogs/machine-learning/build-aws-architecture-diagrams-using-amazon-q-cli-and-mcp/)
