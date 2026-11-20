# Sicurezza e confini di fiducia

Local AppHub è un gestore di servizi **local-first**, non un sistema di isolamento completo.

## Dati privati

- La repository pubblica contiene soltanto codice, esempi generici e documentazione.
- Password hashata, catalogo personale, configurazione, stato e checkout Git risiedono nella cartella dati dell'utente sul PC.
- Non pubblicare token GitHub, `.env`, credenziali, backup o `auth.json`. Per repository private usa il gestore delle credenziali di Git sul PC.
- I cataloghi reali vanno tenuti in una repository privata o solo sul PC.

## Interfaccia e API

- Ascolto predefinito `127.0.0.1:8766`; l'ascolto su reti esterne richiede `--allow-network`.
- Password verificata con PBKDF2-HMAC-SHA256 e salt casuale; la password originale non viene salvata.
- Sessioni con cookie HttpOnly/SameSite Strict, CSRF per azioni, rate limiting, validazione Host contro DNS rebinding.
- Senza CDN e senza HTML generato a partire dai valori del catalogo.
- Le sessioni sono solo in memoria: un riavvio richiede un nuovo login.
- Per un reverse proxy aggiungi l'hostname fidato con `--allowed-host` e usa HTTPS.
- Se manca ancora la password, la prima configurazione web è permessa **solo su localhost**. Non è possibile avviare il servizio in ascolto sulla rete prima di impostarla.

## Deploy e dati

- Le repository devono usare URL `https://github.com/utente/repo`, senza password o token.
- `autoDeploy: true` **autorizza l'esecuzione** del contenuto del repository sul PC tramite Docker. Il valore predefinito è `false`.
- I file Compose hanno percorsi relativi controllati. Non si eseguono comandi Git/Docker attraverso una shell.
- Il rollback dei container non annulla automaticamente modifiche a database o volumi. **Esegui backup prima di upgrade importanti.**
- Lo stop non usa `docker compose down -v`; rimuovere un'app dal catalogo non cancella i suoi dati.
- Dalla dashboard è possibile modificare il catalogo remoto solo tramite un commit Git e un **push senza force**, soggetto ai normali controlli di accesso GitHub. I conflitti remoti non vengono sovrascritti.
- Un altro programma locale con i permessi del tuo utente può leggere i tuoi file anche se la dashboard è protetta da password.

## Limiti della prima versione

- Non sono ancora inclusi backup integrati, autenticazione multiutente, controllo granulare dei permessi Docker, policy sulle immagini o certificati HTTPS automatici.
- Gli snapshot Git vecchi vengono conservati per eventuali ripristini, senza pulizia automatica.
- Gli script Windows e il deploy reale Docker devono ancora essere verificati su un host Windows.
