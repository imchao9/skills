# 空值高危模式

当审查涉及 Java/Kotlin 空值、`Optional`、集合为空或方法链安全性时，读取本文件。这些是经常导致 `NullPointerException`、`NoSuchElementException` 或 `IndexOutOfBoundsException` 的集中风险点。

## NULL-001 `Collectors.toMap` 的 value 可空

- 触发条件：`Collectors.toMap(keyMapper, valueMapper)` 中 `valueMapper` 可能返回 `null`。
- 风险：`HashMap.merge()` 要求 value 非空，可能抛出 `NullPointerException`。
- 问题示例：

```java
map = list.stream().collect(Collectors.toMap(Entity::getKey, Entity::getValue));
```

- 更安全写法：

```java
Map<Long, String> map = new HashMap<>();
list.forEach(e -> map.put(e.getKey(), e.getValue()));
```

```java
map = list.stream()
    .filter(e -> e.getValue() != null)
    .collect(Collectors.toMap(Entity::getKey, Entity::getValue));
```

- 误报边界：如果进入 `toMap` 前已经保证 value 非空，不报告。

## NULL-002 `Optional.get()` / `findFirst().get()`

- 触发条件：直接对 `Optional` 调 `.get()`，包括 `stream().findFirst().get()`。
- 风险：空 `Optional` 会抛出 `NoSuchElementException`。
- 问题示例：

```java
OrderItem item = items.stream().findFirst().get();
```

- 更安全写法：

```java
OrderItem item = items.stream().findFirst().orElse(null);
```

```java
OrderItem item = items.stream().findFirst()
    .orElseThrow(() -> new IllegalStateException("missing item"));
```

- 误报边界：同一路径上紧邻调用前已经证明非空，不报告。

## NULL-003 `Map.get()` 后链式调用

- 触发条件：`map.get(key).foo()` 或类似链式使用。
- 风险：key 不存在时返回 `null`，随后链式访问抛出 `NullPointerException`。
- 问题示例：

```java
amountMap.get(orderId).multiply(rate);
```

- 更安全写法：

```java
BigDecimal amount = amountMap.get(orderId);
if (amount != null) {
    amount.multiply(rate);
}
```

```java
amountMap.getOrDefault(orderId, BigDecimal.ZERO).multiply(rate);
```

- 误报边界：如果该路径能证明 map 对该 key 集合是全量覆盖，不报告。

## NULL-004 可空集合直接 `.stream()`

- 触发条件：`response.getItems().stream()` 或任何返回集合的 getter 被直接 stream。
- 风险：getter 可能返回 `null`，导致 `NullPointerException`。
- 问题示例：

```java
response.getItems().stream().map(Item::getId).collect(toList());
```

- 更安全写法：

```java
Optional.ofNullable(response.getItems())
    .orElse(Collections.emptyList())
    .stream()
    .map(Item::getId)
    .collect(Collectors.toList());
```

- 误报边界：API 契约或本地代码保证返回非空空集合时，不报告。

## NULL-005 包装类型自动拆箱

- 触发条件：`.intValue()`、`.longValue()`、`.booleanValue()`，或可空包装类型参与算术/比较。
- 风险：`Integer`/`Long`/`Boolean` 自动拆箱抛出 `NullPointerException`。
- 问题示例：

```java
if (orderType == 1) { ... }
```

```java
count.intValue();
```

- 更安全写法：

```java
if (Integer.valueOf(1).equals(orderType)) { ... }
```

```java
int safeCount = count == null ? 0 : count;
```

- 误报边界：primitive 或当前路径已归一化的包装类型是安全的。

## NULL-006 `list.get(0)` 没有判空集合

- 触发条件：没有检查 size 或空集合，直接对 list 按下标访问。
- 风险：空 list 抛出 `IndexOutOfBoundsException`。
- 问题示例：

```java
OrderItem first = items.get(0);
```

- 更安全写法：

```java
if (CollectionUtils.isNotEmpty(items)) {
    OrderItem first = items.get(0);
}
```

```java
OrderItem first = items.stream().findFirst().orElse(null);
```

- 误报边界：list 在本地构造且访问前能保证 size，不报告。

## NULL-007 Kotlin `!!`

- 触发条件：非空断言操作符 `!!`。
- 风险：值实际可空时，`!!` 会在运行时抛出 `KotlinNullPointerException`。
- 问题示例：

```kotlin
val id = request.userId!!
```

- 更安全写法：

```kotlin
val id = request.userId ?: return
```

```kotlin
request.userId?.let { id -> handle(id) }
```

- 误报边界：非常窄的互操作代码中，如果前置条件明确且紧邻强制校验，可以接受 `!!`。

## NULL-008 中间节点可空的方法链

- 触发条件：`a.getB().getC().getD()` 这类深链式调用。
- 风险：任意中间节点为 `null` 都会导致 `NullPointerException`。
- 问题示例：

```java
String city = user.getOrganization().getAddress().getCity();
```

- 更安全写法：

```java
Organization org = user.getOrganization();
if (org != null && org.getAddress() != null) {
    return org.getAddress().getCity();
}
```

```java
Optional.ofNullable(user)
    .map(User::getOrganization)
    .map(Organization::getAddress)
    .map(Address::getCity)
    .orElse(null);
```

- 误报边界：如果每一层都由本地构造或明确契约保证非空，不报告。

## NULL-009 `Stream.map()` 产出 `null`

- 触发条件：`stream().map(...)` 的 mapper 可能返回 `null`，后续还有下游操作。
- 风险：后续操作可能抛出 `NullPointerException` 或构造出非法集合。
- 问题示例：

```java
ids.stream()
    .map(idToNameMap::get)
    .collect(Collectors.toList());
```

- 更安全写法：

```java
ids.stream()
    .map(idToNameMap::get)
    .filter(Objects::nonNull)
    .collect(Collectors.toList());
```

- 误报边界：如果下游有意保留 `null` 且没有解引用，视为非问题。

## NULL-010 `BeanUtils.copyProperties` 的 source 可空

- 触发条件：`BeanUtils.copyProperties` 的 source 来自 `Map.get()` 或其他可空 lookup，且没有 guard。
- 风险：source 为 `null`，导致运行时失败或 copy 行为无效。
- 问题示例：

```java
BeanUtils.copyProperties(userMap.get(userId), target);
```

- 更安全写法：

```java
UserEntity source = userMap.get(userId);
if (source != null) {
    BeanUtils.copyProperties(source, target);
}
```

- 误报边界：source 对象在同一路径上已经判空，不报告。
