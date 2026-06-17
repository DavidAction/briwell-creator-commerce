-- Keep keyword CSV imports idempotent.

DELETE FROM keyword_seed newer
USING keyword_seed older
WHERE newer.id > older.id
  AND newer.country = older.country
  AND newer.language = older.language
  AND newer.product_category = older.product_category
  AND newer.intent_type = older.intent_type
  AND newer.keyword IS NOT DISTINCT FROM older.keyword
  AND newer.hashtag IS NOT DISTINCT FROM older.hashtag;

CREATE UNIQUE INDEX IF NOT EXISTS idx_keyword_seed_unique_import
ON keyword_seed (
  country,
  language,
  product_category,
  intent_type,
  COALESCE(keyword, ''),
  COALESCE(hashtag, '')
);
