"""Curated, fictitious seed data per tenant.

All company names, people and streets are invented. ``Kranichfeld
Handelskontor GmbH`` deliberately supplies all three tenants with DIFFERENT
bank details, prices and contract terms: if a tenant ever sees another
tenant's data for this supplier, the cross-tenant leakage probes notice.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class SupplierSeed:
    name: str
    street: str
    post_code: str
    city: str
    contact: str
    language: str = "de"
    payment_terms_days: int = 30


@dataclass(frozen=True)
class ProductSeed:
    name: str
    category: str
    unit: str  # C62 piece, KGM kilogram, XCT carton
    vat: Decimal
    price: Decimal  # list net price per unit
    supplier: int  # index into the tenant's supplier list
    pack_size: int | None = None  # pieces per carton for XCT
    batch: bool = False
    serial: bool = False
    shelf_life_days: int | None = None


SHARED_SUPPLIER = SupplierSeed(
    "Kranichfeld Handelskontor GmbH", "Speicherweg 7", "28195", "Bremen", "Jana Oltmanns"
)

V7 = Decimal(7)
V19 = Decimal(19)

SUPPLIERS: dict[str, list[SupplierSeed]] = {
    "frischemarkt": [
        SupplierSeed("Nordhain Feinkost GmbH", "Am Kornspeicher 12", "24103", "Kiel", "Malte Brodersen"),
        SupplierSeed(
            "Moorwiesen Molkerei eG", "Deichstraße 4", "26655", "Westerstede", "Silke Janßen", "de", 14
        ),
        SupplierSeed("Talbach Obst & Gemüse KG", "Auenring 31", "79539", "Lörrach", "Ercan Yildiz", "de", 10),
        SupplierSeed("Lindengrund Getränke GmbH", "Quellenweg 2", "34117", "Kassel", "Petra Gessler"),
        SupplierSeed(
            "Haselrode Backwaren GmbH", "Mühlenkamp 9", "49074", "Osnabrück", "Tobias Rehm", "de", 7
        ),
        SHARED_SUPPLIER,
    ],
    "technikhaus": [
        SupplierSeed("Voltaris Distribution GmbH", "Industriestraße 88", "63067", "Offenbach", "Daniel Kurz"),
        SupplierSeed(
            "Northgate Components GmbH", "Airport Park 3", "40474", "Düsseldorf", "Olivia Grant", "en", 45
        ),
        SupplierSeed("Pixelwerk Elektronik GmbH", "Lötstraße 15", "90429", "Nürnberg", "Murat Aksoy"),
        SupplierSeed("Kabelhaus Seidl KG", "Gewerbering 6", "84034", "Landshut", "Franziska Seidl", "de", 20),
        SHARED_SUPPLIER,
    ],
    "drogeriewelt": [
        SupplierSeed("Blütenhain Kosmetik GmbH", "Rosengarten 21", "64283", "Darmstadt", "Lea Hartwig"),
        SupplierSeed(
            "Sanavita Pharma Vertrieb GmbH", "Apothekergasse 5", "69117", "Heidelberg", "Jonas Wirth"
        ),
        SupplierSeed(
            "Klarquell Haushaltswaren GmbH", "Seifenweg 18", "42103", "Wuppertal", "Nina Pohl", "de", 45
        ),
        SupplierSeed("Mildwerk Naturpflege GmbH", "Kräuterhof 3", "87435", "Kempten", "Anton Huber"),
        SHARED_SUPPLIER,
    ],
}

PRODUCTS: dict[str, list[ProductSeed]] = {
    "frischemarkt": [
        ProductSeed(
            "Äpfel Elstar lose", "Obst", "KGM", V7, Decimal("1.89"), 2, batch=True, shelf_life_days=30
        ),
        ProductSeed(
            "Bananen Fairtrade lose", "Obst", "KGM", V7, Decimal("1.29"), 2, batch=True, shelf_life_days=10
        ),
        ProductSeed(
            "Tomaten Rispen lose", "Gemüse", "KGM", V7, Decimal("2.49"), 2, batch=True, shelf_life_days=12
        ),
        ProductSeed(
            "Gouda jung am Stück", "Käse", "KGM", V7, Decimal("7.90"), 1, batch=True, shelf_life_days=60
        ),
        ProductSeed(
            "Vollmilch 3,5 % 1 l", "Molkerei", "C62", V7, Decimal("0.89"), 1, batch=True, shelf_life_days=12
        ),
        ProductSeed(
            "Naturjoghurt 500 g", "Molkerei", "C62", V7, Decimal("0.79"), 1, batch=True, shelf_life_days=25
        ),
        ProductSeed(
            "Süßrahmbutter 250 g", "Molkerei", "C62", V7, Decimal("1.69"), 1, batch=True, shelf_life_days=60
        ),
        ProductSeed(
            "Mineralwasser still 12 x 1 l",
            "Getränke",
            "XCT",
            V19,
            Decimal("4.20"),
            3,
            12,
            True,
            shelf_life_days=365,
        ),
        ProductSeed(
            "Apfelsaft naturtrüb 6 x 1 l",
            "Getränke",
            "XCT",
            V19,
            Decimal("6.90"),
            3,
            6,
            True,
            shelf_life_days=365,
        ),
        ProductSeed(
            "Roggenbrot 750 g", "Backwaren", "C62", V7, Decimal("1.95"), 4, batch=True, shelf_life_days=6
        ),
        ProductSeed(
            "Vollkornbrötchen", "Backwaren", "C62", V7, Decimal("0.32"), 4, batch=True, shelf_life_days=3
        ),
        ProductSeed(
            "Freilandeier 10 Stück", "Eier", "C62", V7, Decimal("2.59"), 0, batch=True, shelf_life_days=28
        ),
        ProductSeed(
            "Kaffee gemahlen 500 g",
            "Kolonialwaren",
            "C62",
            V7,
            Decimal("4.99"),
            0,
            batch=True,
            shelf_life_days=540,
        ),
        ProductSeed(
            "Zartbitterschokolade 100 g",
            "Süßwaren",
            "C62",
            V7,
            Decimal("0.95"),
            0,
            batch=True,
            shelf_life_days=365,
        ),
        ProductSeed("Küchenrolle 4 Rollen", "Haushalt", "C62", V19, Decimal("2.10"), 5),
        ProductSeed("Spülmittel 500 ml", "Haushalt", "C62", V19, Decimal("0.85"), 5),
    ],
    "technikhaus": [
        ProductSeed("Smartphone Aria X12 128 GB", "Mobil", "C62", V19, Decimal("389.00"), 0, serial=True),
        ProductSeed("Tablet Aria T10 64 GB", "Mobil", "C62", V19, Decimal("219.00"), 0, serial=True),
        ProductSeed("Notebook Lumen L14 16 GB", "Computer", "C62", V19, Decimal("649.00"), 1, serial=True),
        ProductSeed("Monitor Lumen 27 Zoll QHD", "Computer", "C62", V19, Decimal("229.00"), 1, serial=True),
        ProductSeed("SSD 1 TB NVMe", "Komponenten", "C62", V19, Decimal("64.50"), 1, serial=True),
        ProductSeed("WLAN-Router Mesh AX3000", "Netzwerk", "C62", V19, Decimal("119.00"), 2, serial=True),
        ProductSeed("Smartwatch Pulse 2", "Wearables", "C62", V19, Decimal("149.00"), 2, serial=True),
        ProductSeed("Bluetooth-Kopfhörer ANC", "Audio", "C62", V19, Decimal("79.90"), 2, serial=True),
        ProductSeed("Powerbank 20000 mAh", "Zubehör", "C62", V19, Decimal("24.90"), 2),
        ProductSeed("USB-C-Ladegerät 65 W", "Zubehör", "C62", V19, Decimal("19.90"), 3),
        ProductSeed("HDMI-Kabel 2 m", "Kabel", "C62", V19, Decimal("4.20"), 3),
        ProductSeed("USB-C-Kabel 1 m 10er-Pack", "Kabel", "XCT", V19, Decimal("29.00"), 3, 10),
        ProductSeed("Funktastatur DE-Layout", "Eingabegeräte", "C62", V19, Decimal("27.50"), 4),
        ProductSeed("Funkmaus ergonomisch", "Eingabegeräte", "C62", V19, Decimal("18.90"), 4),
    ],
    "drogeriewelt": [
        ProductSeed(
            "Zahnpasta Kräuter 75 ml",
            "Mundpflege",
            "C62",
            V19,
            Decimal("0.69"),
            0,
            batch=True,
            shelf_life_days=900,
        ),
        ProductSeed(
            "Shampoo Mild 300 ml",
            "Haarpflege",
            "C62",
            V19,
            Decimal("1.29"),
            0,
            batch=True,
            shelf_life_days=900,
        ),
        ProductSeed(
            "Duschgel Sensitiv 250 ml",
            "Körperpflege",
            "C62",
            V19,
            Decimal("0.95"),
            0,
            batch=True,
            shelf_life_days=900,
        ),
        ProductSeed(
            "Handcreme Urea 100 ml",
            "Körperpflege",
            "C62",
            V19,
            Decimal("1.85"),
            3,
            batch=True,
            shelf_life_days=720,
        ),
        ProductSeed(
            "Sonnencreme LSF 30 200 ml",
            "Sonnenschutz",
            "C62",
            V19,
            Decimal("4.95"),
            3,
            batch=True,
            shelf_life_days=540,
        ),
        ProductSeed(
            "Vitamin C Brausetabletten 20 St.",
            "Gesundheit",
            "C62",
            V7,
            Decimal("0.99"),
            1,
            batch=True,
            shelf_life_days=720,
        ),
        ProductSeed(
            "Magnesium Kapseln 60 St.",
            "Gesundheit",
            "C62",
            V7,
            Decimal("3.49"),
            1,
            batch=True,
            shelf_life_days=720,
        ),
        ProductSeed(
            "Babybrei Apfel-Banane 190 g",
            "Baby",
            "C62",
            V7,
            Decimal("0.89"),
            1,
            batch=True,
            shelf_life_days=540,
        ),
        ProductSeed(
            "Pflaster Strips 20 St.",
            "Gesundheit",
            "C62",
            V19,
            Decimal("1.49"),
            1,
            batch=True,
            shelf_life_days=1460,
        ),
        ProductSeed(
            "Vollwaschmittel Pulver 1,35 kg",
            "Haushalt",
            "C62",
            V19,
            Decimal("3.95"),
            2,
            batch=True,
            shelf_life_days=1080,
        ),
        ProductSeed(
            "Taschentücher 24 x 10 St.",
            "Haushalt",
            "XCT",
            V19,
            Decimal("5.40"),
            2,
            24,
            True,
            shelf_life_days=1825,
        ),
        ProductSeed(
            "Deo Roller 50 ml",
            "Körperpflege",
            "C62",
            V19,
            Decimal("1.15"),
            4,
            batch=True,
            shelf_life_days=720,
        ),
        ProductSeed(
            "Rasierklingen 4 St.", "Rasur", "C62", V19, Decimal("5.90"), 4, batch=True, shelf_life_days=1825
        ),
        ProductSeed(
            "Kontaktlinsenlösung 360 ml",
            "Gesundheit",
            "C62",
            V19,
            Decimal("4.25"),
            1,
            batch=True,
            shelf_life_days=540,
        ),
    ],
}

BUYERS: dict[str, SupplierSeed] = {
    "frischemarkt": SupplierSeed(
        "Frischemarkt Handels GmbH", "Marktplatz 1", "30159", "Hannover", "Kreditoren"
    ),
    "technikhaus": SupplierSeed(
        "Technikhaus Retail GmbH", "Schaltweg 20", "70173", "Stuttgart", "Accounts Payable"
    ),
    "drogeriewelt": SupplierSeed("Drogeriewelt Filial GmbH", "Lindenallee 44", "50667", "Köln", "Kreditoren"),
}
