"""CSS selectors — docs/html-field-map.md (05.07.2026 doğrulandı, resmi sözleşme yok)."""

# Liste sayfası
SEARCH_HITS = "div.search--hits"
CARD = "div.card.card--horizontal.card--fundingprogram"
CARD_TITLE_LINK = '.card--title a[href*="Foerderprogramm"]'
CARD_DOC_INFO = "dl.document-info-fundingprogram"
PAGINATION_NEXT = 'a:has-text("weiter")'

# Detay sayfası
DETAIL_TITLE = "h1.title"
DETAIL_DOC_INFO = "dl.document-info-fundingprogram"
DETAIL_TAB1 = "#tab1"
DETAIL_TAB2 = "#tab2"
DETAIL_TAB3 = "#tab3"

# content_hash kaynak blokları (detay)
HASH_SELECTORS = [DETAIL_DOC_INFO, DETAIL_TAB1, DETAIL_TAB2, DETAIL_TAB3]

# Selector health check (detay sayfası)
DETAIL_REQUIRED_SELECTORS = [DETAIL_TITLE, DETAIL_DOC_INFO, DETAIL_TAB1, DETAIL_TAB2, DETAIL_TAB3]

# Liste sayfası health check
LIST_REQUIRED_SELECTORS = [SEARCH_HITS, CARD]
