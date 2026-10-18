# أسماء الدخول المؤسسية للوزارات

أسماء الدخول أدناه تخص هذا التطبيق. استُخدمت اختصارات الجهات المنشورة أو
معرّفات نطاقات مواقعها الحكومية، ولا تعني أنها أسماء دخول مستخدمة في تلك المواقع.
تُكتب بالحروف الكبيرة عند تسجيل الدخول؛ كلمة المرور الحالية لكل حساب تبقى نفسها.

| الوزارة | اسم الدخول السابق | اسم الدخول الجديد | الموقع المرجعي |
| --- | --- | --- | --- |
| النفط | minister.oil | MOO | https://oil.gov.iq/ |
| الكهرباء | minister.electricity | MOELC | https://moelc.gov.iq/ |
| الزراعة | minister.agriculture | MOA | https://zeraa.gov.iq/ |
| الصناعة والمعادن | minister.industry | MIM | https://industry.gov.iq/ |
| التربية | minister.education | MOEDU | https://moedu.gov.iq/ |
| الموارد المائية | minister.water | MOWR | https://mowr.gov.iq/ |
| النقل | minister.transport | MOTRANS | https://motrans.gov.iq/ |
| الخارجية | minister.foreign | MOFA | https://mofa.gov.iq/ |
| المالية | minister.finance | MOF | https://mof.gov.iq/ |
| الاتصالات | minister.communications | MOC | https://moc.gov.iq/ |
| الصحة | minister.health | MOH | https://moh.gov.iq/ |
| البيئة | minister.environment | MOEN | https://moen.gov.iq/ |
| العدل | minister.justice | MOJ | https://moj.gov.iq/ |
| التجارة | minister.trade | MOT | https://mot.gov.iq/ |
| الإعمار والإسكان | acting.construction | MOCH | https://moch.gov.iq/ |
| التخطيط | acting.planning | MOP | https://mop.gov.iq/ |
| الداخلية | acting.interior | MOI | https://moi.gov.iq/ |
| التعليم العالي والبحث العلمي | acting.higher.education | MOHESR | https://mohesr.gov.iq/ |
| الشباب والرياضة | acting.youth | MOYS | https://moys.gov.iq/ |
| الدفاع | acting.defense | MOD | https://mod.mil.iq/ |
| العمل والشؤون الاجتماعية | acting.labor | MOLSA | https://molsa.gov.iq/ |
| الثقافة والسياحة والآثار | acting.culture | MOCUL | https://mocul.gov.iq/ |
| الهجرة والمهجرين | acting.migration | MOMD | https://momd.gov.iq/ |

استخدمنا `MOT` للتجارة و`MOTRANS` للنقل، و`MOC` للاتصالات و`MOCUL` للثقافة،
و`MOELC` للكهرباء و`MOEDU` للتربية لتمييز أسماء الدخول المتشابهة.

مراجع التسمية، روجعت في 18 تشرين الأول 2026:

- [دليل المواقع الحكومية لدى جامعة كركوك](https://uokirkuk.edu.iq/english/index.php/other-services/important-sites).
- [هيئة الاستثمار الوطنية: وزارة النفط (MoO)](https://investpromo.gov.iq/sectors/oil-and-gas-sector/the-role-of-government-in-oil-and-gas/).
- [هيئة الاستثمار الوطنية: وزارة الصناعة والمعادن (MIM)](https://investpromo.gov.iq/sectors/industry-and-manufacturing-sector/industry-and-manufacturing-sector/).
- [وزارة الصحة: وثيقة تستخدم MOH وMOA وMOI](https://moh.gov.iq/upload/997.pdf).
- [وزارة البيئة](https://moen.gov.iq/ar/1)، [وزارة الكهرباء](https://comp.moelc.gov.iq/)، [وزارة التجارة](https://merchant.mot.gov.iq/).

لتطبيق التعديل على نسخة أخرى لديها بيانات حسابات قديمة:

```powershell
python scripts/rename_ministry_usernames.py
```

يعدّل السكربت حقل `username` فقط في حسابات الوزارات المعروفة، ويتحقق من عدم
تكرار الأسماء قبل الكتابة. يمكن تشغيله مجددًا دون تغيير إضافي. تبقى الحسابات
الشخصية ومعرّفات المستخدمين وكلمات المرور والصلاحيات والجلسات وسجلات التدقيق محفوظة.
