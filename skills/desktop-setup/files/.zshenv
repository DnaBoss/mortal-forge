. "$HOME/.cargo/env"
if [ -r "$HOME/.config/agent-pool-gateway/gateway-key" ]; then export AGENT_API_KEY="$(cat "$HOME/.config/agent-pool-gateway/gateway-key")"; fi
