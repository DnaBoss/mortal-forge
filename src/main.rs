mod cache_status;
mod config;
mod repo_policy;
mod service;

use std::{sync::Arc, time::Duration};

use actix_web::{App, HttpResponse, HttpServer, middleware, web};
use rmcp::transport::streamable_http_server::session::local::LocalSessionManager;
use rmcp_actix_web::transport::StreamableHttpService;
use tracing_subscriber::{layer::SubscriberExt, util::SubscriberInitExt};

use crate::{config::load_config, service::MortalService};

async fn health() -> HttpResponse {
    HttpResponse::Ok().json(serde_json::json!({
        "ok": true,
        "service": "mortal-mcp",
        "runtime": "rust"
    }))
}

#[actix_web::main]
async fn main() -> anyhow::Result<()> {
    tracing_subscriber::registry()
        .with(
            tracing_subscriber::EnvFilter::try_from_default_env().unwrap_or_else(|_| "info".into()),
        )
        .with(tracing_subscriber::fmt::layer())
        .init();

    let config = load_config()?;
    let bind = config.bind.clone();
    let mcp_path = config.mcp_path.clone();
    if mcp_path != "/mcp" {
        anyhow::bail!("Only /mcp is supported in the first Rust service cut");
    }

    let service_config = config.clone();
    let mcp_service = StreamableHttpService::builder()
        .service_factory(Arc::new(move || {
            Ok(MortalService::new(service_config.clone()))
        }))
        .session_manager(Arc::new(LocalSessionManager::default()))
        .stateful_mode(false)
        .sse_keep_alive(Duration::from_secs(30))
        .build();

    tracing::info!(bind = %bind, "starting mortal-mcp Rust service");

    HttpServer::new(move || {
        App::new()
            .wrap(middleware::Logger::default())
            .route("/health", web::get().to(health))
            .service(web::scope("/mcp").service(mcp_service.clone().scope()))
    })
    .bind(&bind)?
    .run()
    .await?;

    Ok(())
}
