# Playbook per agenti AI: installa e configura Local AppHub

Questa guida è pensata per Codex, Claude Code, Copilot e altri agenti che possono agire **con autorizzazione** sul PC dell'utente. L'agente deve portare a termine tutto ciò che è verificabile nel suo ambiente, chiedendo input soltanto per scelte personali, autenticazione o operazioni che richiedono privilegi non disponibili.

## Obiettivo di completamento

Una installazione è completata quando:

- la dashboard risponde su `http://127.0.0.1:8766` dal PC;
- l'utente ha creato una password nel browser locale (non comunicandola all'agente);
- Git è operativo e un motore Docker-compatible con Compose è disponibile o la sua mancanza è segnalata chiaramente;
- il catalogo locale o GitHub privato scelto è stato configurato;
- un'app di cui l'utente ha autorizzato il deploy può essere installata o, se non autorizzata, compare soltanto nel catalogo;
- il supervisore di avvio automatico è stato registrato (se richiesto) ed è stato verificato;
- nessun segreto o riferimento personale è stato aggiunto alla repository pubblica.

## 1. Esplora l'ambiente prima di agire

1. Identifica sistema operativo, percorso di lavoro e privilegi correnti. Non assumere che sia Windows.
2. Controlla Git, Python 3.11+, l'accesso alla repository pubblica, Docker CLI, Docker Compose e stato del motore.
3. Su Windows controlla anche WSL2 e virtualizzazione. Se già esiste Rancher Desktop o Docker Desktop funzionante, **riutilizzalo** senza reinstallare.
4. Verifica se Local AppHub è già installato: preserva i file di `%LOCALAPPDATA%\LocalAppHub` e i container esistenti. Non creare un'installazione duplicata.

Controlli PowerShell utili:

```powershell
git --version
py -3 --version
wsl --status
docker compose version
docker info
Get-ScheduledTask -TaskName iPhoneFacile-LocalAppHub -ErrorAction SilentlyContinue
```

Un comando che fallisce è un indizio diagnostico, non un invito a cancellare installazioni esistenti.

## 2. Scegli un motore container aperto

Su Windows 11 preferisci **Rancher Desktop**, progetto open source, con **Moby/dockerd** per esporre Docker CLI e Docker Compose. Rancher Desktop richiede WSL2. Disabilita Kubernetes se non serve, per ridurre il consumo di risorse. È compatibile anche Docker Desktop già installato, ma non è il componente aperto preferito.

- Sito ufficiale: https://rancherdesktop.io/
- Guida ufficiale: https://docs.rancherdesktop.io/getting-started/installation/
- Motore Docker/Moby: https://docs.rancherdesktop.io/ui/preferences/container-engine/general/

La scelta `containerd` + `nerdctl` **non è supportata direttamente** dalla versione attuale, che esegue `docker compose`. Non cambiare motore su una macchina con container già attivi senza spiegare il rischio di rendere invisibili immagini e container esistenti. Se l'installazione di WSL2, Rancher Desktop o Git richiede permessi amministrativi, chiedi la conferma/il normale prompt di sistema. Non aggirare protezioni.

Su Linux usa un Docker Engine/Moby con Compose v2, se già presente. Non installare un motore alternativo senza verificare compatibilità e autorizzazione.

## 3. Installa il controller pubblico

Se il repository non è ancora clonato:

```powershell
git clone https://github.com/emamangiapia/local-apphub.git
cd local-apphub
powershell -ExecutionPolicy Bypass -File .\scripts\install-windows.ps1
```

Se esiste già, verifica `git status` e aggiorna soltanto con `git pull --ff-only` quando non ci sono modifiche locali. Non sovrascrivere progetti o cartelle dell'utente. L'installer configura l'attività pianificata `iPhoneFacile-LocalAppHub` per avviare la piattaforma dopo il login Windows. La password non si imposta più nel terminale: la dashboard presenta un **wizard al primo avvio**.

Per prove senza avvio automatico:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\install-windows.ps1 -NoScheduledTask
py -3 -m apphub serve
```

Linux o altri sistemi: avvia `python -m apphub serve` dalla directory del repository e configura un supervisore di sistema solo previa autorizzazione. Non inventare uno script di installazione Linux supportato se non esiste.

## 4. Completa il wizard nel browser

1. Apri `http://127.0.0.1:8766` **sul PC locale**.
2. L'utente crea la password con il modulo di primo avvio. L'agente non deve leggere, salvare o registrare la password in chat o log.
3. Nella sezione **Gestisci il tuo catalogo**, scegli con l'utente tra configurazione **locale** e repository GitHub **privata**.
4. Se viene scelta la repository privata, chiedi **soltanto l'URL** e il branch/file. La repository deve già esistere o l'utente deve autorizzarne la creazione mediante gli strumenti GitHub normalmente configurati.
5. Se Git richiede autenticazione privata, usa il flusso normale di Git Credential Manager o dell'account; non mettere token negli URL e non modificare il repository pubblico per aggirare il blocco.
6. Premi **Ricontrolla requisiti** e verifica gli indicatori nella dashboard.
7. Se l'utente chiede Local AppHub sul telefono, segui la sezione **Sul telefono** e la guida PWA/Tailscale nel README. Non avviare Tunnel o Serve senza autorizzazione; il proxy privato non deve pubblicare l'hub su Internet.

## 5. Aggiungi e gestisci le app dalla GUI

1. Apri **Applicazioni** e seleziona **Aggiungi app**.
2. Inserisci ID, nome, repository GitHub HTTPS, branch, categoria, file Compose e URL di apertura.
3. Lascia **Installa e aggiorna automaticamente** disattivato salvo autorizzazione esplicita dell'utente e verifica che la repository sia fidata.
4. Verifica che l'app compaia. Se l'utente autorizza, usa **Installa / aggiorna** e attendi il controllo della riuscita del deploy.
5. Per modificare usa **Modifica configurazione**. Per rimuovere, conferma che venga tolta **solo dal catalogo**: container, dati e volumi non sono cancellati automaticamente.
6. In modalità catalogo GitHub privato, ogni modifica viene salvata con **commit e push non forzati**. Se il push fallisce per autenticazione o conflitto, segnala il problema senza riscrivere la cronologia remota.
7. Controlla che gli slot siano univoci e stabili. Una rimozione libera la posizione senza riassociare container o volumi. Al riavvio verifica che i container attesi siano davvero attivi dopo che Docker è pronto, senza riattivare le app messe in pausa nella GUI.

Il motore esegue un controllo ogni 60 secondi. Le app con `autoDeploy: true` vengono installate/aggiornate automaticamente, ma solo finché non sono state fermate manualmente.

## 6. Verifica e consegna

Controlla:

```powershell
Get-ScheduledTask -TaskName iPhoneFacile-LocalAppHub
docker compose version
docker info
```

Da sorgente esegui:

```bash
python -m unittest discover -s tests -v
python -m compileall -q apphub
node --check apphub/static/app.js
```

Verifica la dashboard in un browser e il risultato effettivo del deploy autorizzato. Se Windows, credenziali private, Docker Engine o rete non sono accessibili nel tuo ambiente, segnala il punto esatto da completare senza dichiarare successo.

## Modello di report finale dell'agente

- **Installazione:** completata / da completare (motivo)
- **Dashboard:** indirizzo locale e stato di accessibilità
- **Container:** motore scelto, Compose verificato, stato
- **Catalogo:** locale / privato, senza rivelare dati riservati
- **App:** numero collegate, quante avviate, quante in attesa
- **Avvio automatico:** stato attività pianificata
- **Test:** risultati e limiti
- **Passi rimasti:** soltanto quelli che richiedono il proprietario del PC
