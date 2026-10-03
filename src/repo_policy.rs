//! Read-only adapter for the fixed personal repository Gitflow audit.
use std::{env, path::PathBuf, process::Command};

use anyhow::{Context, Result, bail};
use serde_json::Value;

pub fn repository_path(name: &str) -> Option<PathBuf> {
    let directory = match name {
        "Algo-Lab" | "Easy-PG" | "ExactlyOne" | "Fluke" | "Helios" | "Mortal" | "MortalModel"
        | "agent-pool-gateway" | "aletheia" | "aws-saa" | "essence" | "mortal-mcp" => {
            format!("work_space/private/{name}")
        }
        "board-games" => "work_space/private/chinese-checkers".to_string(),
        "JobResearch" | "game" | "claude-plugins" => format!("work_space/{name}"),
        _ => return None,
    };
    env::var_os("HOME").map(|home| PathBuf::from(home).join(directory))
}

pub fn status(name: &str) -> Result<Value> {
    let repository =
        repository_path(name).context("repository is not in the personal allowlist")?;
    let home = env::var_os("HOME").context("HOME is unavailable")?;
    let script = PathBuf::from(home).join("tools/gitflow-policy/policy.py");
    // The reused audit has three local Git reads, each bounded to five seconds.
    // No arbitrary command/path, credentials, network, or mutation entry is exposed.
    let output = Command::new("python3")
        .arg(script)
        .arg("audit")
        .arg(repository)
        .output()
        .context("failed to execute the installed Gitflow audit")?;
    if !output.status.success() {
        bail!("Gitflow audit failed; inspect the installed CLI for details");
    }
    if output.stdout.len() > 65_536 {
        bail!("Gitflow audit exceeded its output bound");
    }
    serde_json::from_slice(&output.stdout).context("Gitflow audit returned invalid JSON")
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn accepts_personal_names_and_rejects_company_or_arbitrary_paths() {
        assert!(repository_path("Fluke").is_some());
        assert!(repository_path("board-games").is_some());
        for rejected in [
            "account_linker",
            "newretail",
            "sc2-ai-commander",
            "../../etc",
            "/tmp",
        ] {
            assert!(repository_path(rejected).is_none(), "accepted {rejected}");
        }
    }
}
