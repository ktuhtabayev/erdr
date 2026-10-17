# created_date:  16.10.2026
# updated_date:  16.10.2026

Fayllar:
	Spambase (4595, 57, 2) - asosiy versiya.
	Spambase (4204, 57, 2) - (4595, 57, 2) dan takrorlanuvchi qatorlar o'chirilgan versiya.

Obyektlar soni – 4595 ta / 4204 ta.

Alomatlar soni – 57 ta (sinf ustuni bu songa kirmaydi).

!!! 1-satr harakteristik vektor.
!!! Oxirgi satr alomat turlarini ko'rsatadi: 0 - nominal, 1 - miqdoriy.

#######################################################

Alomatlar hususiyatlari:

1...48  - miqdoriy. Xatdagi ma'lum so'zlarning chastotasi (%);

49...54 - miqdoriy. Ma'lum belgilarning chastotasi (%);

55 - miqdoriy. Bosh harflar ketma-ketligining o'rtacha uzunligi;

56 - miqdoriy. Bosh harflar ketma-ketligining eng katta uzunligi;

57 - miqdoriy. Bosh harflarning umumiy soni.

Maqsadli alomat (Target):

58 - nominal.	Sinf:
		(4595, 57, 2): 0 - spam emas (2785 ta), 1 - spam (1810 ta);
		(4204, 57, 2): 1 - spam emas (2528 ta), 2 - spam (1676 ta).

#######################################################

Eslatmalar (16.10.2026, qiymatlar o'zgartirilmagan):

!!! (4595, 57, 2): sinf belgilari 0/1 (boshqa datasetlardagi 1..C emas).
!!! (4595, 57, 2): 391 ta takror qator.
!!! (4595, 57, 2): asl faylda 6 ta bo'sh satr bor edi (65, 150, 480, 1987, 3110, 3215-satrlar).
!!!                UCI versiyasida 4601 ta obyekt bor; bu faylda 6 tasi kam - ehtimol shu
!!!                bo'sh satrlar o'rnidagi obyektlar o'chirilgan.
!!! (4595, 57, 2): asl faylda ma'lumotlardan keyin 2 ta qo'shimcha satr bor edi
!!!                (faqat 1 lardan va 1/5 lardan iborat, sinf 0). Ular obyekt emas,
!!!                shuning uchun shablonga kiritilmagan.

Manba:
https://archive.ics.uci.edu/dataset/94/spambase
