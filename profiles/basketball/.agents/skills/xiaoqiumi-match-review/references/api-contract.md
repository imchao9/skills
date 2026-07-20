# Xiaoqiumi API Contract

The verified API base is `https://api.xiaoqiumi.co/api`.

## CompetitionInfo

Endpoint:

```text
POST https://api.xiaoqiumi.co/api/CompetitionInfo
```

Typical basketball payload:

```json
{"SportType":1,"CompetitionID":400012066}
```

Important fields:

- `data.competitionID`
- `data.seasonID`
- `data.competitionName`
- `data.shortName`
- `data.periods`
- `data.stadium`

## CompPeriodList

Endpoint:

```text
POST https://api.xiaoqiumi.co/api/CompPeriodList
```

Typical payload:

```json
{"SportType":1,"CompetitionID":400012066,"SeasonID":2026,"Mode":1}
```

Important fields:

- `data[].periodID`
- `data[].name`
- `data[].mode`
- `data[].isCuCurrentPeriod`
- `data[].dicList[].name`
- `data[].dicList[].isCuCurrentGroup`

## CompSchedule

Endpoint:

```text
POST https://api.xiaoqiumi.co/api/CompSchedule
```

Typical current-round payload:

```json
{"CompetitionID":400012066,"SportType":1,"Mode":2,"PeriodID":2,"RoundName":"第3轮","GroupId":null}
```

The response stores matches under:

```text
data[].groupScheduleList[]
```

Important match fields:

- `matchID`
- `homeTeamName`
- `awayTeamName`
- `homeScoreAll`
- `awayScoreAll`
- `periodName`
- `roundName`
- `date`
- `stadiumName`
- `status`
- `matchStatus`
- `isHaveRecord`
- `isHaveCollectVideo`

Use this endpoint for matches inside a specific competition.
The generic `MatchList` endpoint can return nearby or global matches and should not be treated as competition-scoped unless verified.

## MatchInfo

Endpoint:

```text
POST https://api.xiaoqiumi.co/api/MatchInfo
```

Typical basketball payload:

```json
{"sportType":1,"MatchID":400365844}
```

Important fields:

- `data.matchID`
- `data.homeTeamName`
- `data.awayTeamName`
- `data.homeScoreAll`
- `data.awayScoreAll`
- `data.competitionName`
- `data.roundName`
- `data.date`
- `data.stadiumName`
- `data.tabs`

## MatchDetail

Endpoint:

```text
POST https://api.xiaoqiumi.co/api/MatchDetail
```

Typical basketball payload:

```json
{"sportType":1,"MatchID":400365844,"tabId":"4529f187-1492-4556-a756-affa52458fd1"}
```

Use `MatchInfo.data.tabs` first.
Known tab ids from previous successful runs are useful fallbacks:

- `4529f187-1492-4556-a756-affa52458fd1`: 赛况.
- `ece45680-f934-4539-92c1-bf42b72238fb`: 数据.
- `818ea8ff-c2f9-4ae8-b41f-8be0e19c2b52`: 阵容.
- `6b59bc76-9d1f-4be3-b697-527422611d3b`: 集锦.

## 赛况 Sections

The `赛况` tab usually stores its useful data under `data.modeData`.

Common sections:

- `比分统计`: period scores and final total.
- `全场最佳`: leaders by scoring, assists, rebounds.
- `全场统计`: scoreboard-style aggregate metrics.
- `篮球球队统计`: team shooting, rebounding, assists, turnovers, steals, fouls, blocks.
- `球员统计`: home and away player box scores.

## Caveats

Page DOM can show zero stats when the H5 page is still loading or blocked.
Prefer API JSON over DOM text for final commentary.

Do not over-interpret extra period fields.
Some match pages show extra columns that should be labeled conservatively as extra periods unless the event log confirms true overtime.

Photo scoreboard data is useful for cross-checking.
If photo data and API data diverge, state the divergence before writing.
