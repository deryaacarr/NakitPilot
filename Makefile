# NakitPilot local Docker helpers
# Usage: make up | make down | make ps | make stop

COMPOSE ?= docker compose
COMPOSE_FLAGS ?= --remove-orphans

.PHONY: up down stop ps logs

## Start the full stack (all 7 services)
up:
	$(COMPOSE) up -d --build $(COMPOSE_FLAGS)

## Stop and remove all project containers + network (keeps volumes/data)
down:
	$(COMPOSE) down $(COMPOSE_FLAGS)
	@# Belt-and-suspenders: anything still named nakitpilot-*
	@ids=$$(docker ps -aq --filter name='^nakitpilot-' 2>/dev/null); \
	if [ -n "$$ids" ]; then docker stop $$ids >/dev/null && docker rm $$ids >/dev/null; fi
	@$(COMPOSE) ps -a

## Pause containers without removing them
stop:
	$(COMPOSE) stop

ps:
	$(COMPOSE) ps -a

logs:
	$(COMPOSE) logs -f --tail=100
