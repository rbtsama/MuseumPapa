# 项目经验积累(Lessons Learned)

> 用途:把项目里遇到的非显然问题、走过的弯路、最终的修法都记在这里。
> 下次撞同类问题,先翻这个文件,避免重复诊断。
>
> 格式约定:每条问题一节,按时间倒序追加。每节四段:
> **症状 / 看似的原因(走过的弯路) / 真因 / 修复 + 防回归**。

---

## 2026-05-14 · Cloudflare 速率限制伪装成 URL 错误

### 症状
`scripts/scrape_dynamic.py` 跑完 57 馆 availability,4 个 Assabet 馆 ok_ratio 异常低:
- `chelsea` 0/8(catastrophic)
- `billerica` 13/19、`carlisle` 12/22、`wayland` 14/20

失败状态全部是 `failed:HTTPError`。其他 48 个 Assabet 馆 100% ok。

### 看似的原因(走过的弯路)
**弯路 1:以为是 URL pattern 出问题**。`chelsea` 0/8 看起来像整个馆的 URL 模板坏了。
**弯路 2:以为是 301 重定向 fetch 处理不了**。手工 `curl -I` 发现这些 URL 都走 `301 → /<slug>/<YYYY-mon>/`,而项目 `http.fetch` 用 `urllib.request.urlopen`。一瞬间以为是 urllib 不跟随 301。

诊断动作:
```python
http.fetch(url, force=True)  # 绕开缓存重抓
```
全部返回 200。`urllib` 默认就跟随 301。**所以诊断陷阱:"看似 0/8 是规律性失败"反而误导。**

### 真因
**Cloudflare 速率限制**(429/503)被伪装成 `urllib.error.HTTPError`。

原 `http.fetch` 的重试逻辑:
```python
except (urllib.error.URLError, TimeoutError, OSError) as e:
    last_err = e
    time.sleep(2**attempt)  # 1s, 2s, 4s = 7s 总 backoff
```

`HTTPError` 是 `URLError` 的子类,所以会进入这条路径。但 7 秒 backoff **撑不过 Cloudflare 30-60 秒的限流窗口**,3 次重试全部撞限流。最后 raise 出去就成了 `failed:HTTPError`。

并发结构:`scrape_library` 用 `ThreadPoolExecutor(max_workers=6)`,每馆 6 并发 × 多 slug × 多 next/next/next/ URL,某些 assabet 子域名压力过大就被 Cloudflare 短暂封 IP。**触发是子域名级、不是全局**:所以只 4 个馆中招、其他 48 馆没事。

### 修复 + 防回归
**1. `src/malibbene/common/http.py`** — 把 `HTTPError` 单独拆出:
```python
except urllib.error.HTTPError as e:
    last_err = e
    if e.code in (429, 503) or 500 <= e.code < 600:
        time.sleep(5 * (3**attempt))  # 5s + 15s + 45s = 65s,够撑过限流
    else:
        break  # 4xx 其他(404 等)立刻放弃,重试无意义
```

**2. `tests/test_http_retry.py`**(5 cases) — monkeypatch 掉 `_fetch_urllib` 和 `time.sleep`,验证:
- 429/503 走长 backoff `[5, 15, 45]`
- 404 立刻 break、`sleeps == []`
- TimeoutError 走原短 backoff `[1, 2, 4]`
- 第一次 429 第二次成功能恢复

**3. 重跑 4 弱馆**:全部恢复到 100% ok。聚合 96.6% → 99.7%,zero libs below 80%。

### 经验
- **HTTPError 不要走通用错误路径**。一个 4xx/5xx 的语义比"网络出错"丰富得多,backoff 策略也该区分。
- **诊断陷阱**:catastrophic 失败(chelsea 0/8)看起来像规律性问题,容易误诊为 URL 模板 / 301 / parser 错。但 Cloudflare 限流的"全失败"也长这样,因为限流一旦触发,后续请求全 429。
- **测试限流 backoff 不需要真等 65 秒**。Monkeypatch `time.sleep` 捕获参数列表就行,几毫秒跑完。
- **HTTP 缓存的边界**:失败的请求不写缓存(成功路径才 `_write_cache`)。所以"重跑"是免费的恢复手段:成功的 944 个 URL 命中缓存秒返,失败的 33 个真重抓 + 长 backoff。

---

## 模板(给后续条目复制)

## YYYY-MM-DD · <一句话标题>

### 症状

### 看似的原因(走过的弯路)

### 真因

### 修复 + 防回归

### 经验
