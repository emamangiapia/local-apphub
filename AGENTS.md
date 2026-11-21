# Local AppHub: istruzioni universali per agenti AI

**Valido per Codex, Claude Code, Copilot e agenti che leggono `AGENTS.md`.**

Questa è la repository **pubblica** di Local AppHub by iPhone Facile (Emanuele Mangiapia). L'obiettivo è che un agente, operando sul PC dell'utente con la sua autorizzazione, possa installare, configurare, verificare e mantenere la piattaforma senza obbligarlo a conoscere comandi o file JSON.

**Segui nell'ordine il playbook completo [`docs/AGENT_AUTOPILOT.md`](docs/AGENT_AUTOPILOT.md).** Contiene controllo dei prerequisiti, installazione Windows, configurazione guidata, verifica del watcher, gestione del catalogo e criteri di completamento. Prima di dichiarare il lavoro concluso, segui la checklist finale.

Regole non negoziabili:

1. Non copiare codice storico, configurazioni, token, nomi delle app private, dati, indirizzi o percorsi personali dalla precedente repository privata.
2. Non chiedere all'utente di comunicare in chat password o token. Le credenziali si configurano tramite l'autenticazione normale del PC/Git e il modulo locale di prima configurazione.
3. Non esporre la dashboard su Internet o sulla LAN senza autorizzazione specifica e protezioni adeguate. La prima configurazione è solo su localhost.
4. Non installare o aggiornare app da repository non fidate senza consenso. `autoDeploy` parte sempre da `false`, attivabile esplicitamente.
5. Non eliminare volumi, container o dati quando un'app sparisce dal catalogo. Non usare `docker compose down -v`.
6. Non eseguire `git reset --hard`, force-push o operazioni che sovrascrivono modifiche locali. Gli aggiornamenti sono fast-forward e i commit al catalogo GitHub privato usano push non forzati.
7. Tieni il catalogo personale in `%LOCALAPPDATA%/LocalAppHub` oppure in una repository GitHub privata distinta. In questa repository soltanto esempi placeholder.
8. Preserva LICENSE PolyForm Noncommercial 1.0.0 e NOTICE attribuendo Emanuele Mangiapia e iPhone Facile.
9. Per la PWA non memorizzare mai nella cache risposte API, cookie, token, credenziali o dati privati. L'accesso remoto usa di default il proxy HTTPS privato Tailscale Serve su `127.0.0.1`, non l'apertura pubblica della dashboard.

Test obbligatori dopo modifiche: `python -m unittest discover -s tests -v`, `python -m compileall -q apphub`, `node --check apphub/static/app.js`, `node --check apphub/static/sw.js` e `node --check apphub/static/theme-init.js`. I temi Retro 8-bit e Liquid devono continuare a funzionare senza asset o servizi esterni.
