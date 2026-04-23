# Optimize Loop - Claude Code Skill

AI自动性能优化循环Skill，实现无限迭代的代码性能优化。

## 功能

- 自动分析代码寻找优化点
- 实现优化并运行benchmark测试
- AI判断性能提升是否显著
- 显著则接受，否则回滚代码
- 无限循环直到手动停止

## 安装

### 方式1：从本地目录安装

在Claude Code中执行：
```
/plugin install /Users/wangshiqin/Desktop/pengfu
```

### 方式2：从Git仓库安装

```bash
# 初始化git仓库
git init
git add .
git commit -m "Initial commit"

# 推送到远程仓库后
/plugin marketplace add <your-username>/pengfu
/plugin install optimize-loop
```

## 使用方法

在Claude Code中执行：
```
/optimize [目标文件或目录]
```

如果不指定目标，默认优化整个项目。

## 工作流程

```
┌──────────────────────────────────────┐
│                                      │
│  ┌─────────────┐                     │
│  │ 保存检查点   │                     │
│  └──────┬──────┘                     │
│         ↓                            │
│  ┌─────────────┐                     │
│  │ 分析优化点   │                     │
│  └──────┬──────┘                     │
│         ↓                            │
│  ┌─────────────┐                     │
│  │ 实现优化    │                     │
│  └──────┬──────┘                     │
│         ↓                            │
│  ┌─────────────┐                     │
│  │ 运行测试    │                     │
│  └──────┬──────┘                     │
│         ↓                            │
│  ┌─────────────┐                     │
│  │ 运行Benchmark│                    │
│  └──────┬──────┘                     │
│         ↓                            │
│  ┌─────────────┐                     │
│  │ 判断提升    │                     │
│  └──────┬──────┘                     │
│         ↓                            │
│    ┌────┴────┐                       │
│    ↓         ↓                       │
│  显著      不显著                     │
│    │         │                       │
│    ↓         ↓                       │
│  提交     回滚                        │
│    │         │                       │
│    └────┬────┘                       │
│         │                            │
│         ↓                            │
│    继续循环...                        │
│                                      │
└──────────────────────────────────────┘
```

## 状态文件

优化过程记录在 `.optimize-state.json`：

```json
{
  "iteration": 10,
  "accepted_optimizations": [...],
  "rejected_optimizations": [...],
  "pending_optimizations": [...],
  "baseline_benchmark": {...},
  "current_benchmark": {...}
}
```

## 示例

```bash
# 在Claude Code中
/optimize bubble_sort.py
```

输出示例：
```
=== 优化循环报告 ===
迭代次数: 5
成功优化: 2
失败尝试: 3
当前性能提升: 15.3%
下一步: 使用更高效的排序算法
```

## 注意事项

1. 确保代码已提交到git，以便回滚
2. 优化过程可能持续很长时间
3. 可随时使用 Ctrl+C 停止
4. 所有优化都会记录在状态文件中
