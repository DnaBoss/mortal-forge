use std::{fs::File, io::Read, path::PathBuf};

use rmcp::{
    ErrorData as McpError, ServerHandler, ServiceExt,
    handler::server::{router::tool::ToolRouter, wrapper::Parameters},
    model::*,
    tool, tool_handler, tool_router,
};
use serde::Deserialize;
use serde_json::{Value, json};

#[derive(Clone)]
struct IndexService {
    path: PathBuf,
    tool_router: ToolRouter<Self>,
}

#[derive(Deserialize, schemars::JsonSchema)]
struct Search {
    query: Option<String>,
    kind: Option<String>,
    limit: Option<usize>,
}

fn search(snapshot: &Value, request: Search) -> Result<Value, McpError> {
    let query = request.query.unwrap_or_default().to_lowercase();
    let limit = request.limit.unwrap_or(20);
    if query.chars().count() > 200 || !(1..=100).contains(&limit) {
        return Err(McpError::invalid_params(
            "Query max 200 characters; limit 1..100",
            None,
        ));
    }
    let items = snapshot["items"]
        .as_array()
        .ok_or_else(|| McpError::internal_error("Invalid index; run ai-tool-index scan", None))?;
    let matches: Vec<_> = items
        .iter()
        .filter(|item| {
            request
                .kind
                .as_ref()
                .is_none_or(|kind| item["kind"] == *kind)
                && item.to_string().to_lowercase().contains(&query)
        })
        .collect();
    Ok(json!({
        "scanned_at": snapshot["scanned_at"],
        "total": matches.len(),
        "items": matches.into_iter().take(limit).collect::<Vec<_>>(),
        "note": "Null means unknown. Installed or enabled does not prove this session loaded it or that it works. Refresh with ai-tool-index scan."
    }))
}

#[tool_router]
impl IndexService {
    fn new(path: PathBuf) -> Self {
        Self {
            path,
            tool_router: Self::tool_router(),
        }
    }

    #[tool(
        description = "Search the local AI tool, Skill, MCP, Plugin and model inventory. Read-only; never executes tools, sends prompts, installs or reads credentials. Null status is unknown."
    )]
    fn ai_tool_index(
        &self,
        Parameters(request): Parameters<Search>,
    ) -> Result<CallToolResult, McpError> {
        let file = File::open(&self.path)
            .map_err(|_| McpError::internal_error("Index missing; run ai-tool-index scan", None))?;
        let mut bytes = Vec::new();
        file.take(16 * 1024 * 1024 + 1)
            .read_to_end(&mut bytes)
            .map_err(|_| McpError::internal_error("Index unreadable", None))?;
        if bytes.len() > 16 * 1024 * 1024 {
            return Err(McpError::internal_error("Index too large", None));
        }
        let snapshot: Value = serde_json::from_slice(&bytes)
            .map_err(|_| McpError::internal_error("Invalid index", None))?;
        Ok(CallToolResult::structured(search(&snapshot, request)?))
    }
}

#[tool_handler(router = self.tool_router)]
impl ServerHandler for IndexService {
    fn get_info(&self) -> ServerConfig {
        ServerConfig::new(ServerCapabilities::builder().enable_tools().build()).with_server_info(
            Implementation::new("ai-tool-index", env!("CARGO_PKG_VERSION")),
        )
    }
}

#[tokio::main]
async fn main() -> anyhow::Result<()> {
    let home = std::env::var_os("HOME").ok_or_else(|| anyhow::anyhow!("HOME missing"))?;
    let path = PathBuf::from(home).join(".local/state/ai-tool-index/snapshot.json");
    let service = IndexService::new(path)
        .serve(rmcp::transport::stdio())
        .await?;
    service.waiting().await?;
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn filter_and_limit_do_not_invent_status() -> Result<(), McpError> {
        let data = json!({"items": [{"name":"jev", "kind":"mcp", "loaded":null}, {"name":"jev-guide", "kind":"skill"}]});
        let result = search(
            &data,
            Search {
                query: Some("jev".into()),
                kind: Some("mcp".into()),
                limit: Some(1),
            },
        )?;
        assert_eq!(result["total"], 1);
        assert_eq!(result["items"][0]["loaded"], Value::Null);
        assert!(
            search(
                &data,
                Search {
                    query: None,
                    kind: None,
                    limit: Some(101)
                }
            )
            .is_err()
        );
        assert!(
            search(
                &json!({}),
                Search {
                    query: None,
                    kind: None,
                    limit: None
                }
            )
            .is_err()
        );
        Ok(())
    }
}
