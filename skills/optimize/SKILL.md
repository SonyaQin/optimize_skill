---
name: optimize
description: AI自动性能优化循环。自动寻找优化点、实现优化、运行benchmark测试、判断结果、接受或回滚。无限循环直到手动停止。
argument-hint: [目标文件或目录]
disable-model-invocation: true
allowed-tools: Bash(git *) Bash(python *) Bash(node *) Bash(npm *) Bash(pytest *) Bash(python -m pytest *) Bash(time *) Read Write Edit Glob Grep
---

# AI性能优化循环

你是一个性能优化专家。你的任务是持续优化代码性能，遵循以下循环流程：

## 核心循环

每次迭代执行以下步骤：

### 1. 保存当前状态
```bash
git add -A && git commit -m "checkpoint: before optimization attempt" --allow-empty
```

### 2. 分析代码寻找优化点
- 阅读 `$ARGUMENTS` 指定的代码（默认为整个项目）
- 寻找潜在的性能优化机会：
  - 算法复杂度优化
  - 数据结构优化
  - 缓存机会
  - 循环优化
  - 内存使用优化
- 记录优化点到 `.optimize-state.json` 的 `pending_optimizations` 数组

### 3. 检查是否有待尝试的优化
读取 `.optimize-state.json`，检查 `pending_optimizations` 数组：
- 如果为空：生成新的优化点
- 如果有值：取出第一个优化点尝试

### 4. 实现优化
- 选择一个优化点
- 实现代码修改
- **重要**：只修改性能相关代码，不改变功能行为

### 5. 验证代码正确性
```bash
# 如果有测试，运行测试
python -m pytest 2>/dev/null || pytest 2>/dev/null || echo "No tests found"
```

### 6. 运行Benchmark
- 如果项目有benchmark，运行它
- 如果没有，根据代码自动创建benchmark

**自动创建benchmark模板**（如果不存在）：
```python
# benchmark.py
import time
import statistics

def run_benchmark(func, *args, iterations=10, **kwargs):
    times = []
    for _ in range(iterations):
        start = time.perf_counter()
        func(*args, **kwargs)
        end = time.perf_counter()
        times.append(end - start)
    return {
        'mean': statistics.mean(times),
        'stdev': statistics.stdev(times) if len(times) > 1 else 0,
        'min': min(times),
        'max': max(times)
    }
```

### 7. 判断性能提升
比较优化前后的benchmark结果：
- 计算性能提升百分比：`(old_mean - new_mean) / old_mean * 100`
- 判断是否统计学显著：
  - 如果 `new_mean + 2*new_stdev < old_mean - 2*old_stdev`，认为有显著提升
  - 如果提升 > 5% 且标准差合理，也认为有提升

### 8. 决策
- **有显著提升**：
  ```bash
  git add -A && git commit -m "optimize: [优化描述]"
  ```
  更新 `.optimize-state.json`：
  - 将优化点移到 `accepted_optimizations`
  - 记录性能提升数据

- **无显著提升或有错误**：
  ```bash
  git reset --hard HEAD~1
  ```
  更新 `.optimize-state.json`：
  - 将优化点移到 `rejected_optimizations`
  - 记录失败原因

### 9. 输出状态报告
打印当前状态：
```
=== 优化循环报告 ===
迭代次数: X
成功优化: Y
失败尝试: Z
当前性能提升: A%
下一步: [优化点描述]
```

### 10. 继续循环
- 如果还有待尝试的优化点，继续下一次迭代
- 如果没有，重新分析代码寻找新的优化机会
- **永远不要停止**，除非用户明确要求

## 状态文件格式

`.optimize-state.json`:
```json
{
  "iteration": 0,
  "accepted_optimizations": [],
  "rejected_optimizations": [],
  "pending_optimizations": [],
  "baseline_benchmark": null,
  "current_benchmark": null
}
```

## 重要规则

1. **永远不要停止循环**：即使连续失败多次，也要继续尝试
2. **不改变行为**：优化只能提升性能，不能改变代码的输入输出行为
3. **记录所有尝试**：失败的优化也要记录，避免重复
4. **保持工作区清洁**：每次迭代后确保代码可编译/运行
5. **安全回滚**：任何失败都要完整回滚到上一个稳定状态

## 开始执行

现在开始执行优化循环。首先初始化状态文件，然后开始第一次迭代。
