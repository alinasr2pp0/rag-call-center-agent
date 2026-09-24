# التقييم والمقاييس (Evaluation & Metrics)

مرجع واحد لكل مقاييس الأداء والتقييم الخاصة بمشروع RAG Call Center Agent —
إزاي تتحسب، من فين في الداتابيز، والهدف المقترح لكل واحدة.

---

## 1. مقاييس النتيجة النهائية (Business KPIs)

هي المقاييس اللي بتوصف نجاح النظام ككل، مبنية على الأهداف الأصلية للمشروعين
اللي اتدمجوا فيه (Outbound Calls FCR + KB Chatbot).

| المقياس | التعريف | الهدف المقترح | مصدر الحساب |
|---|---|---|---|
| **FCR Rate** (First Call Resolution) | نسبة التذاكر اللي اتأكد حلها من أول مكالمة متابعة (من غير Retry تاني) | ≥ 90% | `tickets.status = 'resolved_confirmed'` ÷ إجمالي التذاكر اللي وصلها مكالمة |
| **Text-Resolution Rate** | نسبة التذاكر اللي اتحلت من أول رد نصي (KB) من غير الحاجة لمكالمة أصلاً | يُقاس، لا يوجد هدف ثابت بعد | `tickets.status = 'resolved_by_rag'` وقت الرد الأول |
| **Escalation Rate** | نسبة التذاكر اللي اتصعدت لموظف بشري | ≤ 15% | `tickets.status = 'escalated'` ÷ إجمالي التذاكر |
| **Call Completion Rate** | نسبة المكالمات اللي اتعملت بالكامل عن طريق AI من غير تحويل | ≥ 85% | `calls.outcome != 'transferred_to_agent'` ÷ إجمالي المكالمات |
| **Average Handle Time (AHT)** | متوسط مدة المكالمة الواحدة | يُقاس، هدف مبدئي < 90 ثانية | متوسط `calls.duration_seconds` |
| **Time to First Answer** | الوقت بين إرسال العميل للمشكلة واستلامه أول رد نصي | < 5 ثواني | فرق التوقيت بين `messages` (customer) و`messages` (agent) الأولى |
| **Web-Search Fallback Rate** | نسبة الحالات اللي احتاجت بحث إنترنت (يعني الـ KB متغطيش المشكلة) | يُقاس — مؤشر على فجوات الـ KB | `resolutions.source = 'web_search'` ÷ إجمالي المحاولات |
| **Call Reachability Rate** | نسبة المكالمات اللي اترد عليها من أول مرة (من غير retry) | يُقاس | `calls.retry_count = 0 AND status = 'completed'` ÷ إجمالي المكالمات |

### استعلامات SQL جاهزة

```sql
-- FCR Rate
SELECT
  COUNT(*) FILTER (WHERE status = 'resolved_confirmed')::float
  / NULLIF(COUNT(*) FILTER (WHERE status IN ('resolved_confirmed','escalated')), 0) AS fcr_rate
FROM tickets;

-- Escalation Rate
SELECT
  COUNT(*) FILTER (WHERE status = 'escalated')::float / NULLIF(COUNT(*), 0) AS escalation_rate
FROM tickets;

-- Average Handle Time
SELECT AVG(duration_seconds) AS avg_handle_time_seconds FROM calls WHERE duration_seconds IS NOT NULL;

-- Web-search fallback rate
SELECT
  COUNT(*) FILTER (WHERE source = 'web_search')::float / NULLIF(COUNT(*), 0) AS web_search_rate
FROM resolutions;
```

(نفس الأرقام دي متاحة جاهزة عبر `GET /admin/stats` للأساسيات، وممكن تضيف endpoint خاص بالباقي لو احتجتها في اللوحة.)

---

## 2. تقييم جودة الـ RAG (KB Retrieval + Generation)

هنا بنقيس دقة النظام في حل المشكلة فعليًا، مش بس إنه "رد حاجة".

| المقياس | التعريف | إزاي يتقاس |
|---|---|---|
| **Retrieval Precision@k** | من ضمن أول k نتائج مسترجعة من Pinecone، كام منها فعلاً مرتبط بالمشكلة | تقييم يدوي على عينة أسئلة معروف إجابتها الصحيحة (Golden Set) |
| **Answer Confidence Distribution** | توزيع قيم `confidence_score` المسجلة في `resolutions` | `SELECT confidence_score FROM resolutions WHERE source='kb'` — لو أغلب القيم واطية، الـ KB محتاج تحسين |
| **Hallucination Rate** | نسبة الردود اللي الـ LLM اقترح فيها `kb_article_id` مش موجود أصلاً في النتائج المسترجعة | مقاس بالفعل تلقائيًا في الكود (`resolution_agent._try_kb`) — راقب الفرق بين الـ id المقترح والمستخدم فعليًا في اللوجات |
| **Category Coverage** | هل كل تصنيفات المشاكل الشائعة عندها مقالات KB كافية | `SELECT category, COUNT(*) FROM kb_articles GROUP BY category` — قارنها بتوزيع المشاكل الفعلية من `tickets.category` |

**طريقة تقييم مقترحة (Golden Set):**
1. اعمل ملف بـ 30-50 سؤال حقيقي متوقع من العملاء، مع الإجابة الصحيحة المتوقعة لكل واحد.
2. شغّل كل سؤال على `/tickets/message` وسجّل: هل استرجع المقال الصح؟ هل الإجابة مطابقة؟
3. احسب: `دقة = عدد الإجابات الصحيحة ÷ إجمالي الأسئلة`.
4. كرر الاختبار ده كل ما تضيف مقالات جديدة للـ KB، عشان تتأكد إنك مش بتكسر حاجة قديمة.

---

## 3. تقييم دقة التصنيف أثناء المكالمة

| المقياس | التعريف | إزاي يتقاس |
|---|---|---|
| **Confirmation Classification Accuracy** | دقة `llm.classify_call_response` في تحديد هل رد العميل يعني "اتحلت" أو "لأ" | راجع عينة من `calls.transcript` يدويًا وقارن بالـ outcome المسجل |
| **False Positive Resolution Rate** | نسبة التذاكر اللي اتقفلت "resolved_confirmed" لكن العميل رجع بنفس المشكلة تاني (تذكرة جديدة بنفس الفئة من نفس العميل خلال فترة قصيرة) | Query مقارنة بين `tickets` لنفس `customer_id` بفارق زمني قصير |

```sql
-- تذاكر مشتبه فيها كـ "حل كاذب" (نفس العميل، نفس الفئة، خلال 7 أيام من إغلاق سابق)
SELECT t2.id AS reopened_ticket, t1.id AS original_ticket
FROM tickets t1
JOIN tickets t2 ON t1.customer_id = t2.customer_id
  AND t1.category = t2.category
  AND t2.opened_at BETWEEN t1.closed_at AND t1.closed_at + INTERVAL '7 days'
WHERE t1.status = 'resolved_confirmed';
```

---

## 4. مقاييس الموثوقية التشغيلية (Reliability)

| المقياس | التعريف | مصدر الحساب |
|---|---|---|
| **Call Dispatch Latency** | الفرق بين `calls.scheduled_at` و`calls.started_at` الفعلي | لازم يكون قريب من `CALL_DISPATCH_POLL_SECONDS` (10 ثانية) كحد أقصى تقريبًا |
| **Retry Exhaustion Rate** | نسبة المكالمات اللي استهلكت كل الـ retries (busy/no-answer) قبل ما توصل | `calls.retry_count >= MAX_CALL_RETRIES` ÷ إجمالي المكالمات |
| **LLM Fallback Trigger Rate** | كام مرة الموديل الأساسي فشل واحتجنا الـ fallback chain | مش متسجل حاليًا في الداتابيز — يُنصح بإضافة log عند كل fallback (تحسين مستقبلي) |
| **API Error Rate** | نسبة الطلبات اللي رجعت خطأ من أي خدمة خارجية (Voyage/Pinecone/OpenRouter/Tavily/Vonage) | يُنصح بإضافة structured logging (تحسين مستقبلي، مش موجود في النسخة الحالية) |

---

## 5. جودة الصوت (ASR/TTS)

ملحوظة: Vonage بيتولى التعرف على الصوت (ASR) وتوليد الصوت (TTS) بنفسه عبر NCCO — مفيش خدمة STT/TTS منفصلة في الكود حاليًا. المقاييس دي بتتقاس من عينة مكالمات حقيقية.

| المقياس | التعريف |
|---|---|
| **Word Error Rate (WER)** | نسبة الكلمات الغلط في نص الـ STT مقارنة بالكلام الفعلي — يتقاس بعينة صوتية مُراجَعة يدويًا |
| **TTS Naturalness (MOS)** | تقييم بشري (1-5) لطبيعية الصوت الناتج — عينة عشوائية من المكالمات |

---

## 6. جدول متابعة دوري مقترح

| المقياس | التكرار |
|---|---|
| FCR Rate, Escalation Rate, AHT | أسبوعي |
| Golden Set evaluation للـ RAG | عند كل إضافة/تعديل KB article |
| مراجعة يدوية لعينة من المكالمات (Confirmation Classification Accuracy) | أسبوعي (10-15 مكالمة عشوائية) |
| Category Coverage | شهري |

---

## 7. حالة التنفيذ الحالية

- ✅ كل الجداول والحقول المطلوبة لحساب المقاييس دي موجودة فعليًا في `schema.sql`
  (بعد إصلاحات المراجعة الأخيرة: `kb_article_id`/`web_search_log_id` بقوا
  متسجلين صح، `ticket.category` بيتحدد تلقائيًا)
- ✅ `GET /admin/stats` بيدي أساسيات (total/resolved/escalated/open) جاهزة فورًا
- ⏳ باقي الاستعلامات في الملف ده لسه يدوية (SQL مباشر) — لو عايز، نقدر نضيفها
  كـ endpoints جاهزة في `/admin` أو تقرير دوري مُصدَّر تلقائيًا
- ⏳ الـ Golden Set evaluation وWER/MOS محتاجين عملية يدوية/سكريبت منفصل، مش
  جزء من الكود الحالي
