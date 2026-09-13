# CrazyGames
Проверено: 2026-09-13. Статус: публичные правила прочитаны; допуск конкретной игры не проверен.

## Источники
- [Developer portal docs](https://docs.crazygames.com/), [Basic Launch](https://docs.crazygames.com/resources/basic-launch-metrics/).
- [Общие требования](https://docs.crazygames.com/requirements/intro/), [технические](https://docs.crazygames.com/requirements/technical/), [реклама](https://docs.crazygames.com/requirements/ads/).
- [Лидерборды](https://docs.crazygames.com/sdk/leaderboards/), [server API](https://docs.crazygames.com/sdk/leaderboard-api/), [FAQ](https://docs.crazygames.com/faq/).

## Два режима, не путать
Basic Launch — тест без рекламной/IAP-монетизации; SDK необязателен. Публично описано окно 7–21 день, обычно до выполнения минимальных 7 дней и 500 plays, но это не обещание трафика или Full Launch.
Full Launch — отдельное принятие площадкой и SDK-интеграция. Создать разные профили basic/full, не оставлять в basic платные кнопки и тупики «смотреть рекламу для продолжения».

## Размер и SDK
Публичные ограничения: initial download до 50 MB, total до 250 MB, до 1500 файлов; без SDK применяется отдельное ограничение total 50 MB. Условие initial ≤20 MB касается допуска на мобильную главную, не всех загрузок.
В итоговом QA отдельно измерить загрузку до первого gameplay, а не принять размер ZIP за initial. Перепроверить числа перед отправкой.
Документацию методов искать из актуального SDK-индекса по движку и версии; не угадывать URL/старые сигнатуры. Передавать точный gameplay lifecycle. Ads только разрешённым SDK; no-fill не ломает игру. Сохранения/аккаунт использовать по требованиям выбранного релизного режима.

## IAP и leaderboard
Покупки доступны по приглашению/допуску, через утверждённый платежный маршрут. Пока допуска нет — feature disabled, не строить MVP вокруг магазина.
Native leaderboard также **invite-only**; публичная страница описывает одну таблицу на игру. Не добавлять её по одному желанию пользователя без подтверждения доступа. Существование native API не означает, что выбранный bridge поддерживает его.
Backend API ключ хранится на сервере; не внедрять его в WebGL/JS. Клиентская таблица требует признать риск подмены результатов; не обещать античит.

## QA и профиль
Указать basic/full, список разрешённых функций, размер и measured initial download, game ID, SDK/provider version, account/save strategy, ads placements. В кабинете проверить статус принятия и выполнить preview lifecycle/ad tests; IAP/board — только при подтверждённой доступности.
Cross-platform release разрешается правилами FAQ при наличии прав; всё равно проверить индивидуальный договор и платёжный маршрут из России. В архиве нет утверждения, что конкретный банк/контрагент принят.
