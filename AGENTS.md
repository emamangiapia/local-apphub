# Local AppHub: istruzioni per contributori e agenti

Questa è la versione pubblica di **Local AppHub by iPhone Facile**, Emanuele Mangiapia. Non copiare configurazioni, segreti o cronologia dalla precedente repository privata.

1. Mantieni fuori da Git credenziali, file `.env`, indirizzi personali, nomi delle app private, percorsi dell'utente e dati di installazione.
2. Il catalogo delle applicazioni deve rimanere personale: sul PC o in una repository GitHub privata separata. Pubblica solo esempi neutri.
3. Preserva i dati: non eliminare automaticamente volumi o container quando un'app viene rimossa dal catalogo.
4. Richiedi `autoDeploy: true` esplicito, e rispetta la pausa manuale.
5. Modifiche ad autenticazione, accesso di rete e deploy richiedono test appropriati.
6. Mantieni intatti gli avvisi di licenza PolyForm Noncommercial 1.0.0 e l'attribuzione a Emanuele Mangiapia.

Test: `python -m unittest discover -s tests -v`, `python -m compileall -q apphub`, `node --check apphub/static/app.js`.
