use std::{env, fs, path::PathBuf};

use anyhow::{Context, Result};
use serde::{Deserialize, Serialize};

#[derive(Clone, Debug, Default, Deserialize, Serialize)]
pub struct ServiceConfig {
    #[serde(default = "default_bind")]
    pub bind: String,
    #[serde(default = "default_mcp_path")]
    pub mcp_path: String,
    #[serde(default)]
    pub companies: Vec<CompanyConfig>,
}

#[derive(Clone, Debug, Deserialize, Serialize)]
pub struct CompanyConfig {
    pub id: String,
    pub name: String,
    #[serde(default)]
    pub tools: Vec<ToolConfig>,
}

#[derive(Clone, Debug, Deserialize, Serialize)]
pub struct ToolConfig {
    pub name: String,
    pub purpose: String,
    #[serde(default)]
    pub adapter: AdapterConfig,
    #[serde(default)]
    pub read_only: bool,
}

#[derive(Clone, Debug, Default, Deserialize, Serialize)]
#[serde(tag = "kind", rename_all = "snake_case")]
pub enum AdapterConfig {
    #[default]
    NotImplemented,
    ExistingShell {
        command: String,
        #[serde(default)]
        args: Vec<String>,
    },
    McpTool {
        tool: String,
    },
}

fn default_bind() -> String {
    "127.0.0.1:18765".to_string()
}

fn default_mcp_path() -> String {
    "/mcp".to_string()
}

pub fn load_config() -> Result<ServiceConfig> {
    let Some(path) = env::var_os("MORTAL_CONFIG") else {
        return Ok(ServiceConfig {
            bind: default_bind(),
            mcp_path: default_mcp_path(),
            companies: Vec::new(),
        });
    };
    let path = PathBuf::from(path);
    let text = fs::read_to_string(&path)
        .with_context(|| format!("failed to read MORTAL_CONFIG at {}", path.display()))?;
    serde_json::from_str(&text)
        .with_context(|| format!("failed to parse MORTAL_CONFIG at {}", path.display()))
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn parses_multi_company_catalog_config() {
        let config: ServiceConfig = serde_json::from_str(
            r#"{
              "bind": "127.0.0.1:18766",
              "mcp_path": "/mcp",
              "companies": [
                {
                  "id": "alpha",
                  "name": "Alpha Co",
                  "tools": [
                    {
                      "name": "status",
                      "purpose": "Read status",
                      "adapter": {"kind": "mcp_tool", "tool": "status"},
                      "read_only": true
                    }
                  ]
                },
                {
                  "id": "beta",
                  "name": "Beta Co",
                  "tools": []
                }
              ]
            }"#,
        )
        .expect("valid service config");

        assert_eq!(config.bind, "127.0.0.1:18766");
        assert_eq!(config.companies.len(), 2);
        assert_eq!(config.companies[0].tools[0].name, "status");
        assert!(config.companies[0].tools[0].read_only);
    }
}
