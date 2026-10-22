use std::sync::Arc;

use rmcp::{
    ErrorData as McpError, RoleServer, ServerHandler,
    handler::server::{router::tool::ToolRouter, wrapper::Parameters},
    model::*,
    service::RequestContext,
    tool, tool_handler, tool_router,
};
use serde::Deserialize;
use serde_json::json;

use crate::config::ServiceConfig;

#[derive(Clone)]
pub struct MortalService {
    config: Arc<ServiceConfig>,
    #[allow(
        dead_code,
        reason = "The rmcp #[tool_handler] macro reads this field through Self::tool_router()."
    )]
    tool_router: ToolRouter<MortalService>,
}

#[derive(Debug, Deserialize, schemars::JsonSchema)]
struct CatalogRequest {
    company_id: Option<String>,
    query: Option<String>,
    limit: Option<usize>,
}

#[tool_router]
impl MortalService {
    pub fn new(config: ServiceConfig) -> Self {
        Self {
            config: Arc::new(config),
            tool_router: Self::tool_router(),
        }
    }

    #[tool(description = "Return MORTAL MCP service readiness and configured company count.")]
    fn mortal_health(&self) -> Result<CallToolResult, McpError> {
        Ok(CallToolResult::structured(json!({
            "ok": true,
            "service": "mortal-mcp",
            "runtime": "rust",
            "companies": self.config.companies.len(),
            "note": "Health only proves the MCP service is answering; it is not downstream acceptance."
        })))
    }

    #[tool(description = "List configured companies that this MCP service can route tools for.")]
    fn mortal_companies(&self) -> Result<CallToolResult, McpError> {
        let companies: Vec<_> = self
            .config
            .companies
            .iter()
            .map(|company| {
                json!({
                    "id": company.id,
                    "name": company.name,
                    "tools": company.tools.len()
                })
            })
            .collect();
        Ok(CallToolResult::structured(json!({
            "ok": true,
            "companies": companies
        })))
    }

    #[tool(
        description = "Search the configured tool catalog. This does not execute shell, MCP tools, DB, or remote actions."
    )]
    fn mortal_catalog(
        &self,
        Parameters(request): Parameters<CatalogRequest>,
    ) -> Result<CallToolResult, McpError> {
        let limit = request.limit.unwrap_or(20).clamp(1, 50);
        let query = request.query.unwrap_or_default().to_lowercase();
        let company_filter = request.company_id.as_deref();
        let mut tools = Vec::new();

        for company in &self.config.companies {
            if let Some(company_id) = company_filter
                && company.id != company_id
            {
                continue;
            }
            for tool in &company.tools {
                let haystack = format!(
                    "{} {} {} {}",
                    company.id, company.name, tool.name, tool.purpose
                )
                .to_lowercase();
                if !query.is_empty() && !haystack.contains(&query) {
                    continue;
                }
                tools.push(json!({
                    "company_id": company.id,
                    "company": company.name,
                    "name": tool.name,
                    "purpose": tool.purpose,
                    "read_only": tool.read_only,
                    "adapter": tool.adapter
                }));
                if tools.len() >= limit {
                    break;
                }
            }
            if tools.len() >= limit {
                break;
            }
        }

        Ok(CallToolResult::structured(json!({
            "ok": true,
            "total": tools.len(),
            "tools": tools,
            "note": "Catalog text is not executable. Use a purpose-built adapter tool for bounded operations."
        })))
    }
}

#[tool_handler]
impl ServerHandler for MortalService {
    fn get_info(&self) -> ServerConfig {
        ServerConfig::new(
            ServerCapabilities::builder()
                .enable_tools()
                .enable_resources()
                .build(),
        )
        .with_server_info(Implementation::new("mortal-mcp", env!("CARGO_PKG_VERSION")))
        .with_instructions(
            "MORTAL MCP routes installable skills to bounded project tools. \
             It supports multiple companies through explicit configuration and does not expose arbitrary shell, SQL, or remote-host execution.",
        )
    }

    async fn list_resources(
        &self,
        _request: Option<PaginatedRequestParams>,
        _: RequestContext<RoleServer>,
    ) -> Result<ListResourcesResult, McpError> {
        Ok(ListResourcesResult::with_all_items(vec![
            Resource::new("mortal://skills/mortal-tools", "mortal-tools skill"),
            Resource::new("mortal://skills/fluke-ops", "fluke operations skill"),
        ]))
    }

    async fn read_resource(
        &self,
        ReadResourceRequestParams { uri, .. }: ReadResourceRequestParams,
        _: RequestContext<RoleServer>,
    ) -> Result<ReadResourceResponse, McpError> {
        let text = match uri.as_str() {
            "mortal://skills/mortal-tools" => include_str!("../skills/mortal-tools/SKILL.md"),
            "mortal://skills/fluke-ops" => include_str!("../skills/fluke-ops/SKILL.md"),
            _ => {
                return Err(McpError::resource_not_found(
                    "resource_not_found",
                    Some(json!({ "uri": uri })),
                ));
            }
        };
        Ok(ReadResourceResult::new(vec![ResourceContents::text(text, uri)]).into())
    }
}
