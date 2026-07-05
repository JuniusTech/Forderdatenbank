# Schreiben an moysies & partners — Nutzungsanfrage Förderdatenbank

**Status:** Entwurf — vor Versand prüfen und anpassen  
**An:** foerderdatenbank@moysies.de  
**Betreff:** Anfrage zur kommerziellen Nutzung der Förderdatenbank-Daten in einer Beratungssoftware

---

## E-Mail-Entwurf (Deutsch)

```
Sehr geehrte Damen und Herren,

mein Name ist [VORNAME NACHNAME], [POSITION] bei [FIRMENNAME].
Wir entwickeln eine interne Beratungssoftware für gastronomische
Unternehmen in Deutschland, die diese bei der Suche nach passenden
Förderprogrammen unterstützt (Culinary Funding OS).

Impressum der Förderdatenbank zufolge betreiben Sie die Redaktion
und Pflege der Datenbank im Auftrag des Bundesministeriums für
Wirtschaft und Energie.

Wir möchten die öffentlich zugänglichen Programmdaten der
Förderdatenbank in unsere Software integrieren und haben dazu
einige Fragen, um unsere Nutzung rechtskonform zu gestalten:

1. TECHNISCHER ZUGRIFF
   Wir haben festgestellt, dass der früher dokumentierte XML-Export
   unter /FDB/WS/export nicht mehr verfügbar ist. Beabsichtigen Sie,
   einen maschinenlesbaren Datenzugang (API, Export, Feed) anzubieten
   oder zu empfehlen? Falls ja, wie kann man diesen beantragen?

2. AUTOMATISIERTE DATENABRUFUNG
   Wir planen einen respektvollen, robots.txt-konformen Crawler
   (Crawl-delay: 30 Sekunden), der ausschließlich die öffentlichen
   Förderprogramm-Seiten abruft und die HTML-Inhalte unverändert
   archiviert. Ist eine solche Nutzung aus Ihrer Sicht zulässig?

3. LIZENZ CC BY-ND 4.0 DE
   Laut Impressum stehen die Inhalte unter CC BY-ND 4.0 DE. Wir
   verstehen „Keine Bearbeitung" (ND) so, dass wir die Originaltexte
   unverändert speichern dürfen. Unsere Software würde darüber hinaus:
   - strukturierte Metadaten extrahieren (Förderart, Region, Zielgruppe)
   - interne Schlagwörter für die Programmsuche generieren
   - KEINE veränderten oder zusammengefassten Texte gegenüber
     Endnutzern veröffentlichen

   Ist diese Form der maschinellen Verarbeitung im Sinne der ND-Klausel
   zulässig? Falls nicht, welche Nutzungsform würden Sie empfehlen?

4. KOMMERZIELLE NUTZUNG
   Die Software dient der internen Beratung durch Fachkräfte — nicht
   der Weiterverbreitung der Datenbankinhalte. Endnutzer sehen
   Programmvorschläge mit Verweis auf die Förderdatenbank als Quelle
   und den Hinweis „Maßgeblich sind die Angaben auf den offiziellen
   Webseiten der fördergebenden Stellen." Ist eine solche kommerzielle
   Beratungsnutzung mit Quellenangabe zulässig?

5. QUELLENANGABE
   Wir planen folgende Attribution pro Datensatz:
   „Quelle: Förderdatenbank des Bundes und der Länder
   (https://www.foerderdatenbank.de), Lizenz: CC BY-ND 4.0 DE"
   Ist diese Formulierung aus Ihrer Sicht korrekt und ausreichend?

Wir würden uns über eine schriftliche Stellungnahme freuen, bevor wir
die Datenverarbeitung in Produktion nehmen. Selbstverständlich halten
wir uns an alle von Ihnen genannten Auflagen.

Mit freundlichen Grüßen

[VORNAME NACHNAME]
[POSITION]
[FIRMENNAME]
[ADRESSE]
[E-MAIL]
[TELEFON]
```

---

## Begleitende Notizen (intern, nicht mitsenden)

### Was wir mit der Antwort erreichen wollen

| Frage | Ideales Ergebnis |
|-------|------------------|
| API/Export | Offizieller Zugang → Crawler überflüssig |
| Crawling | Schriftliche Erlaubnis oder Stillschweigende Duldung |
| BY-ND + AI | Klarstellung: strukturierte Extraktion ≠ Bearbeitung |
| Kommerziell | Beratungssoftware mit Quellenangabe ist OK |
| Attribution | Bestätigung der Formulierung |

### Falls keine Antwort innerhalb von 4 Wochen

- Crawler trotzdem starten (robots.txt-konform, ND-lizenzkonform)
- Faz 3 (AI Normalizer) bis zur Antwort **nicht** in Produktion
- Rechtsberatung für BY-ND + maschinelle Verarbeitung einholen

### Anhänge (optional)

- Screenshots der geplanten Quellenangabe in der UI
- Kurzbeschreibung Culinary Funding OS (1 Seite)

---

## Türkçe Özet (iç kullanım)

Bu taslak moysies & partners'e gönderilecek resmi Almanca yazışmadır. Beş ana soru:

1. XML export yok — resmi API var mı?
2. robots.txt uyumlu crawler izinli mi?
3. BY-ND kapsamında yapılandırılmış metadata çıkarma (AI normalizer) izinli mi?
4. Ticari danışmanlık yazılımında kullanım OK mi?
5. Attribution metni doğru mu?

**Senin yapman gereken:** `[KÖŞELİ PARANTEZ]` alanlarını doldur, gözden geçir, gönder.
