"""Minimal liste sayfası HTML — parser unit testleri için (gerçek DOM yapısı)."""

LIST_PAGE_FIXTURE = """
<!DOCTYPE html>
<html>
<body>
<div class="search--hits">2.488 Beiträge</div>
<div class="card card--horizontal card--fundingprogram">
  <div class="card--title"><a href="/FDB/Content/DE/Foerderprogramm/Bund/test-programm.html">Test Programm A</a></div>
  <dl class="document-info-fundingprogram">
    <dt>Wer wird gefördert?:</dt><dd>Kleine und mittlere Unternehmen</dd>
    <dt>Was wird gefördert?:</dt><dd>Digitalisierung</dd>
  </dl>
</div>
<div class="card card--horizontal card--fundingprogram">
  <div class="card--title"><a href="/FDB/Content/DE/Foerderprogramm/Land/Berlin/berlin-programm.html">Test Programm B</a></div>
  <dl class="document-info-fundingprogram">
    <dt>Wer wird gefördert?:</dt><dd>Start-ups</dd>
    <dt>Was wird gefördert?:</dt><dd>Gründung</dd>
  </dl>
</div>
<a href="/SiteGlobals/FDB/Forms/Suche/Startseitensuche_Formular.html?gtp=2">weiter</a>
</body>
</html>
"""

DETAIL_PAGE_FIXTURE = """
<!DOCTYPE html>
<html>
<body>
<h1 class="title">Test Förderprogramm</h1>
<dl class="document-info-fundingprogram">
  <dt>Förderart:</dt><dd>Zuschuss</dd>
  <dt>Förderbereich:</dt><dd>Digitalisierung</dd>
  <dt>Fördergebiet:</dt><dd>Bund</dd>
  <dt>Förderberechtigte:</dt><dd>KMU</dd>
  <dt>Ansprechpunkt:</dt><dd class="card"><div class="card--title">Test Bank</div></dd>
</dl>
<article class="content--tab-text" id="tab1"><h2>Kurztext</h2><p>Kurze Beschreibung.</p></article>
<article class="content--tab-text" id="tab2"><h2>Rechtliche Voraussetzungen</h2><ul><li>KMU unter 250 MA</li></ul></article>
<article class="content--tab-text" id="tab3"><h2>Richtlinie</h2><p>Voller Richtlinientext.</p></article>
</body>
</html>
"""
