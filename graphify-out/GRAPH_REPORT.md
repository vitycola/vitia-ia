# Graph Report - /Users/victor/Documents/CodeProjects/vitia-ia/.claude/worktrees/reverent-germain-4e734f  (2026-07-13)

## Corpus Check
- Corpus is ~5,894 words - fits in a single context window. You may not need a graph.

## Summary
- 200 nodes · 431 edges · 21 communities (15 shown, 6 thin omitted)
- Extraction: 97% EXTRACTED · 3% INFERRED · 0% AMBIGUOUS · INFERRED: 15 edges (avg confidence: 0.58)
- Token cost: 0 input · 0 output

## Community Hubs (Navigation)
- [[_COMMUNITY_OpenFoodFacts Adapter|OpenFoodFacts Adapter]]
- [[_COMMUNITY_JWT Auth Layer|JWT Auth Layer]]
- [[_COMMUNITY_Claude LLM Adapter|Claude LLM Adapter]]
- [[_COMMUNITY_Config and Settings|Config and Settings]]
- [[_COMMUNITY_Test Fixtures|Test Fixtures]]
- [[_COMMUNITY_Food Matcher Service|Food Matcher Service]]
- [[_COMMUNITY_Food Route Tests|Food Route Tests]]
- [[_COMMUNITY_Food Domain Models|Food Domain Models]]
- [[_COMMUNITY_Vercel Deploy Config|Vercel Deploy Config]]
- [[_COMMUNITY_README API Docs|README API Docs]]
- [[_COMMUNITY_CI Deploy Workflow|CI Deploy Workflow]]
- [[_COMMUNITY_Project Metadata|Project Metadata]]
- [[_COMMUNITY_Env Vars Reference|Env Vars Reference]]
- [[_COMMUNITY_CI Pipeline Root|CI Pipeline Root]]

## God Nodes (most connected - your core abstractions)
1. `IdentifiedFoods` - 22 edges
2. `MacrosPer100g` - 19 edges
3. `FoodMatcherService` - 19 edges
4. `Settings` - 18 edges
5. `MacroTotals` - 18 edges
6. `ClaudeAdapter` - 16 edges
7. `verify_jwt()` - 16 edges
8. `IdentifiedFood` - 14 edges
9. `make_token()` - 13 edges
10. `get_settings()` - 12 edges

## Surprising Connections (you probably didn't know these)
- `test_identified_foods_default_empty()` --calls--> `IdentifiedFoods`  [EXTRACTED]
  tests/test_food_model.py → src/domain/food.py
- `test_analyze_image_includes_vision_prompt()` --calls--> `ClaudeAdapter`  [EXTRACTED]
  tests/test_claude_adapter.py → src/adapters/claude_adapter.py
- `test_analyze_image_returns_identified_foods()` --calls--> `ClaudeAdapter`  [EXTRACTED]
  tests/test_claude_adapter.py → src/adapters/claude_adapter.py
- `test_analyze_image_sends_base64_block()` --calls--> `ClaudeAdapter`  [EXTRACTED]
  tests/test_claude_adapter.py → src/adapters/claude_adapter.py
- `test_parse_text_includes_text_prompt_and_user_text()` --calls--> `ClaudeAdapter`  [EXTRACTED]
  tests/test_claude_adapter.py → src/adapters/claude_adapter.py

## Import Cycles
- None detected.

## Communities (21 total, 6 thin omitted)

### Community 0 - "OpenFoodFacts Adapter"
Cohesion: 0.14
Nodes (23): OFFFallbackClient, Query OFF v1 CGI search; return MacrosPer100g for first usable product, or None., GenericFoodRepository, Search generic_foods by ilike on name_normalized. Returns up to 10 rows., AsyncClient, BaseModel, MacrosPer100g, MacroTotals (+15 more)

### Community 1 - "JWT Auth Layer"
Cohesion: 0.14
Nodes (18): get_current_user(), AuthError, _get_jwks_client(), Return a cached PyJWKClient instance for the given JWKS URL., Decode and verify an ES256 JWT using JWKS. Raises AuthError on any failure., verify_jwt(), CurrentUser, FastAPI (+10 more)

### Community 2 - "Claude LLM Adapter"
Cohesion: 0.13
Nodes (17): ClaudeAdapter, LLMAdapter, AsyncAnthropic, IdentifiedFoods, Protocol, SimpleNamespace, apple_client(), make_mock_client() (+9 more)

### Community 3 - "Config and Settings"
Cohesion: 0.15
Nodes (18): get_llm_adapter(), BaseSettings, MonkeyPatch, Settings, settings(), Tests for Settings startup validator and JWT aud/iss verification (T10)., A token with wrong aud claim must raise AuthError., A token with correct aud and iss must decode successfully. (+10 more)

### Community 4 - "Test Fixtures"
Cohesion: 0.17
Nodes (21): EllipticCurvePrivateKey, EllipticCurvePublicKey, TestClient, ec_public_key(), make_token(), test_expired_token(), test_health_still_public(), test_malformed_token() (+13 more)

### Community 5 - "Food Matcher Service"
Cohesion: 0.16
Nodes (15): Exception, normalize(), Lowercase and strip accents (NFD decomposition, remove Mn category)., _foods(), _make_service(), Unit tests for FoodMatcherService., One matched item + one unmatched: totals reflect only matched actuals., test_both_miss_unmatched() (+7 more)

### Community 6 - "Food Route Tests"
Cohesion: 0.16
Nodes (15): degraded_service(), _make_app_no_service(), _make_app_with_service(), matched_service(), Integration tests for POST /food/match., POST /food/match without Authorization header returns 401., POST /food/match with a tampered token returns 401., Service that returns one matched item per food in the payload. (+7 more)

### Community 7 - "Food Domain Models"
Cohesion: 0.36
Nodes (8): IdentifiedFood, _make_food(), test_confidence_above_one_rejected(), test_confidence_below_zero_rejected(), test_estimated_grams_negative_rejected(), test_estimated_grams_zero_rejected(), test_identified_foods_default_empty(), test_valid_identified_food()

## Knowledge Gaps
- **9 isolated node(s):** `vitia-ia`, `builds`, `routes`, `CI Pipeline`, `Check Job (lint+test)` (+4 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **6 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `IdentifiedFoods` connect `Claude LLM Adapter` to `OpenFoodFacts Adapter`, `Food Matcher Service`, `Food Domain Models`?**
  _High betweenness centrality (0.199) - this node is a cross-community bridge._
- **Why does `get_settings()` connect `JWT Auth Layer` to `OpenFoodFacts Adapter`, `Config and Settings`?**
  _High betweenness centrality (0.110) - this node is a cross-community bridge._
- **Why does `ClaudeAdapter` connect `Claude LLM Adapter` to `Config and Settings`?**
  _High betweenness centrality (0.093) - this node is a cross-community bridge._
- **Are the 3 inferred relationships involving `IdentifiedFoods` (e.g. with `ClaudeAdapter` and `LLMAdapter`) actually correct?**
  _`IdentifiedFoods` has 3 INFERRED edges - model-reasoned connections that need verification._
- **Are the 2 inferred relationships involving `MacrosPer100g` (e.g. with `OFFFallbackClient` and `FoodMatcherService`) actually correct?**
  _`MacrosPer100g` has 2 INFERRED edges - model-reasoned connections that need verification._
- **Are the 8 inferred relationships involving `FoodMatcherService` (e.g. with `OFFFallbackClient` and `GenericFoodRepository`) actually correct?**
  _`FoodMatcherService` has 8 INFERRED edges - model-reasoned connections that need verification._
- **What connects `vitia-ia`, `Query OFF v1 CGI search; return MacrosPer100g for first usable product, or None.`, `Search generic_foods by ilike on name_normalized. Returns up to 10 rows.` to the rest of the system?**
  _26 weakly-connected nodes found - possible documentation gaps or missing edges._