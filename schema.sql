-- ============================================================
-- ChurnRadar – Schéma de base de données (SQLite)
-- ============================================================

-- ------------------------------------------------------------
-- Tables
-- ------------------------------------------------------------

CREATE TABLE IF NOT EXISTS clients (
    client_id        INTEGER PRIMARY KEY,
    nom              TEXT    NOT NULL,
    email            TEXT    UNIQUE NOT NULL,
    ville            TEXT    NOT NULL,
    date_inscription DATE    NOT NULL,
    segment          TEXT    NOT NULL
);

CREATE TABLE IF NOT EXISTS commandes (
    commande_id   INTEGER PRIMARY KEY,
    client_id     INTEGER NOT NULL REFERENCES clients(client_id),
    date_commande DATE    NOT NULL,
    montant       REAL    NOT NULL,
    statut        TEXT    NOT NULL
);

CREATE TABLE IF NOT EXISTS sessions (
    session_id   INTEGER PRIMARY KEY,
    client_id    INTEGER NOT NULL REFERENCES clients(client_id),
    date_session DATE    NOT NULL,
    duree_sec    INTEGER NOT NULL,
    pages_vues   INTEGER NOT NULL,
    source       TEXT    NOT NULL
);

CREATE TABLE IF NOT EXISTS churn_scores (
    client_id          INTEGER PRIMARY KEY REFERENCES clients(client_id),
    score_churn        REAL    NOT NULL,
    segment_risque     TEXT    NOT NULL,
    date_calcul        DATE    NOT NULL,
    jours_inactif      INTEGER NOT NULL,
    nb_commandes       INTEGER NOT NULL,
    panier_moyen       REAL    NOT NULL,
    action_recommandee TEXT    NOT NULL
);

-- ------------------------------------------------------------
-- Vue résumé client
-- ------------------------------------------------------------

CREATE VIEW IF NOT EXISTS v_client_resume AS
SELECT
    c.client_id,
    c.nom,
    c.email,
    c.ville,
    c.date_inscription,
    c.segment,
    COUNT(DISTINCT cmd.commande_id)                                                           AS nb_commandes,
    COALESCE(ROUND(SUM(cmd.montant), 2), 0)                                                   AS chiffre_affaires,
    COALESCE(ROUND(AVG(cmd.montant), 2), 0)                                                   AS panier_moyen,
    MAX(cmd.date_commande)                                                                    AS derniere_commande,
    COUNT(DISTINCT s.session_id)                                                              AS nb_sessions,
    COALESCE(ROUND(AVG(s.duree_sec), 0), 0)                                                  AS duree_session_moyenne,
    MAX(s.date_session)                                                                       AS derniere_session,
    CAST(JULIANDAY('now') - JULIANDAY(
        COALESCE(MAX(s.date_session), c.date_inscription)
    ) AS INTEGER)                                                                             AS jours_inactif
FROM clients c
LEFT JOIN commandes cmd ON cmd.client_id = c.client_id
LEFT JOIN sessions   s  ON s.client_id   = c.client_id
GROUP BY c.client_id, c.nom, c.email, c.ville, c.date_inscription, c.segment;

-- ============================================================
-- Données fictives – 30 clients français
-- Profils : actifs (1-10), inactifs (11-20), très inactifs (21-30)
-- ============================================================

INSERT INTO clients VALUES
-- Actifs : dernière activité < 14 jours
(1,  'Marie Dupont',       'marie.dupont@gmail.com',        'Paris',              '2024-03-15', 'Particulier'),
(2,  'Thomas Martin',      'thomas.martin@pme-lyon.fr',     'Lyon',               '2023-11-20', 'PME'),
(3,  'Sophie Bernard',     'sophie.bernard@startup.io',     'Marseille',          '2024-01-08', 'Startup'),
(4,  'Lucas Petit',        'lucas.petit@gmail.com',         'Toulouse',           '2024-04-12', 'Particulier'),
(5,  'Emma Moreau',        'emma.moreau@grandgroupe.fr',    'Nantes',             '2023-08-05', 'Grand compte'),
(6,  'Hugo Leroy',         'hugo.leroy@pme-alsace.fr',      'Strasbourg',         '2024-02-28', 'PME'),
(7,  'Camille Simon',      'camille.simon@gmail.com',       'Bordeaux',           '2024-04-01', 'Particulier'),
(8,  'Théo Laurent',       'theo.laurent@betastudio.io',    'Lille',              '2023-12-10', 'Startup'),
(9,  'Léa Robert',         'lea.robert@gmail.com',          'Rennes',             '2024-05-20', 'Particulier'),
(10, 'Antoine Girard',     'antoine.girard@pme-cote.fr',    'Nice',               '2024-03-03', 'PME'),
-- Inactifs : dernière activité 15-60 jours
(11, 'Pauline Michel',     'pauline.michel@gmail.com',      'Montpellier',        '2023-05-18', 'Particulier'),
(12, 'Maxime Thomas',      'maxime.thomas@artisan38.fr',    'Grenoble',           '2023-07-22', 'PME'),
(13, 'Chloé Dubois',       'chloe.dubois@nextwave.io',      'Dijon',              '2023-09-14', 'Startup'),
(14, 'Nicolas Fontaine',   'nicolas.fontaine@gmail.com',    'Reims',              '2023-04-30', 'Particulier'),
(15, 'Alice Mercier',      'alice.mercier@enterprise.fr',   'Angers',             '2023-06-15', 'Grand compte'),
(16, 'Julien Blanc',       'julien.blanc@gmail.com',        'Tours',              '2023-10-08', 'Particulier'),
(17, 'Manon Henry',        'manon.henry@pme-limousin.fr',   'Limoges',            '2023-03-25', 'PME'),
(18, 'Pierre Rousseau',    'pierre.rousseau@gmail.com',     'Metz',               '2023-08-19', 'Particulier'),
(19, 'Laura Garnier',      'laura.garnier@picardie.io',     'Amiens',             '2023-11-05', 'Startup'),
(20, 'Kévin Morin',        'kevin.morin@gmail.com',         'Clermont-Ferrand',   '2023-02-14', 'Particulier'),
-- Très inactifs : dernière activité > 60 jours
(21, 'Isabelle Faure',     'isabelle.faure@gmail.com',      'Caen',               '2022-09-10', 'Particulier'),
(22, 'Sébastien Perrin',   'sebastien.perrin@pme45.fr',     'Orléans',            '2022-11-28', 'PME'),
(23, 'Nathalie Bonnet',    'nathalie.bonnet@gmail.com',     'Besançon',           '2022-07-15', 'Particulier'),
(24, 'Romain Dupuis',      'romain.dupuis@labtech.io',      'Poitiers',           '2022-12-03', 'Startup'),
(25, 'Valérie Colin',      'valerie.colin@holding76.fr',    'Rouen',              '2022-05-22', 'Grand compte'),
(26, 'Éric Leclerc',       'eric.leclerc@gmail.com',        'Brest',              '2022-08-17', 'Particulier'),
(27, 'Stéphanie Vidal',    'stephanie.vidal@pme-var.fr',    'Toulon',             '2022-10-09', 'PME'),
(28, 'François Denis',     'francois.denis@gmail.com',      'Perpignan',          '2022-03-28', 'Particulier'),
(29, 'Céline Marty',       'celine.marty@gmail.com',        'Le Havre',           '2022-06-14', 'Particulier'),
(30, 'Olivier Roux',       'olivier.roux@normantech.io',    'Nancy',              '2022-04-05', 'Startup');

-- ------------------------------------------------------------
-- Commandes
-- ------------------------------------------------------------

INSERT INTO commandes VALUES
-- Client 1 – Marie Dupont (actif)
(1,  1,  '2026-05-26', 145.50, 'en_cours'),
(2,  1,  '2026-05-20',  89.90, 'livree'),
(3,  1,  '2026-03-10',  67.00, 'livree'),
-- Client 2 – Thomas Martin (actif)
(4,  2,  '2026-05-22', 450.00, 'en_cours'),
(5,  2,  '2026-05-15', 320.00, 'livree'),
(6,  2,  '2026-04-02', 280.00, 'livree'),
-- Client 3 – Sophie Bernard (actif)
(7,  3,  '2026-05-27',  99.00, 'en_cours'),
(8,  3,  '2026-05-18', 210.00, 'livree'),
(9,  3,  '2026-04-25', 175.00, 'livree'),
-- Client 4 – Lucas Petit (actif)
(10, 4,  '2026-05-20',  78.50, 'livree'),
(11, 4,  '2026-05-14',  55.00, 'livree'),
-- Client 5 – Emma Moreau (actif)
(12, 5,  '2026-05-21', 1200.00, 'en_cours'),
(13, 5,  '2026-05-10',  890.00, 'livree'),
(14, 5,  '2026-04-15',  750.00, 'livree'),
(15, 5,  '2026-03-20',  640.00, 'livree'),
-- Client 6 – Hugo Leroy (actif)
(16, 6,  '2026-05-23', 210.00, 'en_cours'),
(17, 6,  '2026-05-16', 380.00, 'livree'),
-- Client 7 – Camille Simon (actif)
(18, 7,  '2026-05-25',  88.00, 'en_cours'),
(19, 7,  '2026-05-19',  62.00, 'livree'),
(20, 7,  '2026-04-05',  45.00, 'livree'),
-- Client 8 – Théo Laurent (actif)
(21, 8,  '2026-05-26', 310.00, 'en_cours'),
(22, 8,  '2026-05-14', 195.00, 'livree'),
(23, 8,  '2026-04-18', 155.00, 'livree'),
-- Client 9 – Léa Robert (actif)
(24, 9,  '2026-05-22',  95.00, 'livree'),
(25, 9,  '2026-05-17',  73.00, 'livree'),
-- Client 10 – Antoine Girard (actif)
(26, 10, '2026-05-24', 290.00, 'livree'),
(27, 10, '2026-05-15', 415.00, 'en_cours'),
(28, 10, '2026-04-28', 360.00, 'livree'),
-- Client 11 – Pauline Michel (inactif)
(29, 11, '2026-04-15',  45.00, 'livree'),
(30, 11, '2026-03-10',  67.00, 'livree'),
-- Client 12 – Maxime Thomas (inactif)
(31, 12, '2026-04-20', 220.00, 'livree'),
-- Client 13 – Chloé Dubois (inactif)
(32, 13, '2026-04-28',  85.00, 'livree'),
(33, 13, '2026-04-05', 130.00, 'livree'),
-- Client 14 – Nicolas Fontaine (inactif)
(34, 14, '2026-04-12',  58.00, 'livree'),
-- Client 15 – Alice Mercier (inactif)
(35, 15, '2026-04-18', 680.00, 'livree'),
(36, 15, '2026-03-25', 920.00, 'livree'),
-- Client 16 – Julien Blanc (inactif)
(37, 16, '2026-04-30', 110.00, 'livree'),
-- Client 17 – Manon Henry (inactif)
(38, 17, '2026-04-08', 275.00, 'livree'),
(39, 17, '2026-03-15', 195.00, 'livree'),
-- Client 18 – Pierre Rousseau (inactif)
(40, 18, '2026-04-22',  40.00, 'livree'),
-- Client 19 – Laura Garnier (inactif)
(41, 19, '2026-04-10', 165.00, 'livree'),
-- Client 20 – Kévin Morin (inactif)
(42, 20, '2026-04-25',  52.00, 'livree'),
(43, 20, '2026-03-18',  88.00, 'livree'),
-- Client 21 – Isabelle Faure (très inactif)
(44, 21, '2026-01-15',  95.00, 'livree'),
-- Client 22 – Sébastien Perrin (très inactif)
(45, 22, '2025-12-20', 340.00, 'livree'),
(46, 22, '2025-11-05', 280.00, 'livree'),
-- Client 23 – Nathalie Bonnet : aucune commande
-- Client 24 – Romain Dupuis (très inactif)
(47, 24, '2026-02-10', 120.00, 'livree'),
-- Client 25 – Valérie Colin (très inactif)
(48, 25, '2026-01-08', 1100.00, 'livree'),
(49, 25, '2025-12-15',  890.00, 'livree'),
-- Client 26 – Éric Leclerc : aucune commande
-- Client 27 – Stéphanie Vidal (très inactif)
(50, 27, '2026-02-25', 310.00, 'livree'),
-- Client 28 – François Denis : aucune commande
-- Client 29 – Céline Marty (très inactif)
(51, 29, '2026-01-20',  65.00, 'livree'),
-- Client 30 – Olivier Roux (très inactif)
(52, 30, '2026-02-05', 180.00, 'livree'),
(53, 30, '2025-11-25', 220.00, 'annulee');

-- ------------------------------------------------------------
-- Sessions
-- ------------------------------------------------------------

INSERT INTO sessions VALUES
-- Client 1 – Marie Dupont (actif)
(1,  1,  '2026-05-26', 180,  4, 'direct'),
(2,  1,  '2026-05-20', 320,  8, 'email'),
(3,  1,  '2026-05-01', 540, 12, 'search'),
(4,  1,  '2026-04-15', 210,  6, 'social'),
-- Client 2 – Thomas Martin (actif)
(5,  2,  '2026-05-22', 360,  8, 'direct'),
(6,  2,  '2026-05-15', 480, 10, 'email'),
(7,  2,  '2026-04-10', 720, 15, 'search'),
-- Client 3 – Sophie Bernard (actif)
(8,  3,  '2026-05-27', 190,  5, 'direct'),
(9,  3,  '2026-05-18', 240,  6, 'social'),
(10, 3,  '2026-05-05', 420,  9, 'email'),
-- Client 4 – Lucas Petit (actif)
(11, 4,  '2026-05-20', 280,  7, 'search'),
(12, 4,  '2026-05-14', 150,  3, 'direct'),
-- Client 5 – Emma Moreau (actif)
(13, 5,  '2026-05-21', 680, 18, 'email'),
(14, 5,  '2026-05-10', 520, 14, 'direct'),
(15, 5,  '2026-04-15', 890, 22, 'referral'),
(16, 5,  '2026-03-20', 750, 19, 'email'),
-- Client 6 – Hugo Leroy (actif)
(17, 6,  '2026-05-23', 310,  8, 'direct'),
(18, 6,  '2026-05-16', 430, 11, 'email'),
(19, 6,  '2026-04-28', 560, 13, 'search'),
-- Client 7 – Camille Simon (actif)
(20, 7,  '2026-05-25', 145,  4, 'email'),
(21, 7,  '2026-05-19', 190,  5, 'social'),
(22, 7,  '2026-05-03', 320,  8, 'direct'),
-- Client 8 – Théo Laurent (actif)
(23, 8,  '2026-05-26', 290,  7, 'direct'),
(24, 8,  '2026-05-14', 380,  9, 'email'),
(25, 8,  '2026-04-18', 450, 11, 'search'),
-- Client 9 – Léa Robert (actif)
(26, 9,  '2026-05-22', 210,  5, 'social'),
(27, 9,  '2026-05-17', 175,  4, 'email'),
(28, 9,  '2026-05-08', 390,  9, 'direct'),
-- Client 10 – Antoine Girard (actif)
(29, 10, '2026-05-24', 380,  9, 'direct'),
(30, 10, '2026-05-15', 510, 12, 'email'),
(31, 10, '2026-04-28', 620, 15, 'referral'),
-- Client 11 – Pauline Michel (inactif)
(32, 11, '2026-04-20', 280,  6, 'email'),
(33, 11, '2026-03-15', 190,  4, 'direct'),
-- Client 12 – Maxime Thomas (inactif)
(34, 12, '2026-04-25', 370,  8, 'email'),
(35, 12, '2026-04-05', 220,  5, 'search'),
-- Client 13 – Chloé Dubois (inactif)
(36, 13, '2026-04-28', 160,  3, 'email'),
(37, 13, '2026-04-10', 195,  5, 'social'),
-- Client 14 – Nicolas Fontaine (inactif)
(38, 14, '2026-04-15', 240,  6, 'direct'),
-- Client 15 – Alice Mercier (inactif)
(39, 15, '2026-04-20', 580, 14, 'email'),
(40, 15, '2026-03-28', 690, 17, 'direct'),
-- Client 16 – Julien Blanc (inactif)
(41, 16, '2026-05-01', 175,  4, 'email'),
(42, 16, '2026-04-12', 280,  7, 'social'),
-- Client 17 – Manon Henry (inactif)
(43, 17, '2026-04-12', 320,  8, 'email'),
(44, 17, '2026-03-20', 280,  6, 'direct'),
-- Client 18 – Pierre Rousseau (inactif)
(45, 18, '2026-04-25', 140,  3, 'email'),
-- Client 19 – Laura Garnier (inactif)
(46, 19, '2026-04-15', 230,  5, 'social'),
(47, 19, '2026-03-22', 195,  4, 'email'),
-- Client 20 – Kévin Morin (inactif)
(48, 20, '2026-05-05', 170,  4, 'direct'),
(49, 20, '2026-04-10', 215,  5, 'email'),
-- Client 21 – Isabelle Faure (très inactif)
(50, 21, '2026-01-20', 180,  4, 'email'),
(51, 21, '2025-12-10', 120,  3, 'direct'),
-- Client 22 – Sébastien Perrin (très inactif)
(52, 22, '2026-01-05', 340,  8, 'email'),
(53, 22, '2025-11-20', 280,  6, 'direct'),
-- Client 23 – Nathalie Bonnet (très inactif)
(54, 23, '2025-12-15',  95,  2, 'email'),
-- Client 24 – Romain Dupuis (très inactif)
(55, 24, '2026-02-15', 220,  5, 'social'),
(56, 24, '2026-01-10', 180,  4, 'email'),
-- Client 25 – Valérie Colin (très inactif)
(57, 25, '2026-01-10', 640, 16, 'email'),
(58, 25, '2025-12-20', 590, 15, 'direct'),
-- Client 26 – Éric Leclerc (très inactif)
(59, 26, '2025-12-05', 145,  3, 'email'),
-- Client 27 – Stéphanie Vidal (très inactif)
(60, 27, '2026-02-28', 310,  7, 'email'),
(61, 27, '2026-01-15', 275,  6, 'direct'),
-- Client 28 – François Denis (très inactif)
(62, 28, '2025-11-20',  85,  2, 'email'),
-- Client 29 – Céline Marty (très inactif)
(63, 29, '2026-01-25', 155,  4, 'email'),
(64, 29, '2025-12-08', 110,  3, 'direct'),
-- Client 30 – Olivier Roux (très inactif)
(65, 30, '2026-02-10', 245,  6, 'email'),
(66, 30, '2025-12-15', 210,  5, 'social');

-- ------------------------------------------------------------
-- Scores de churn (calculés au 2026-05-28)
-- ------------------------------------------------------------

INSERT INTO churn_scores VALUES
-- Actifs – risque faible (score 0.06-0.15)
(1,  0.0850, 'faible',   '2026-05-28',   2,  3,  100.80, 'Newsletter fidélité + offre personnalisée'),
(2,  0.1200, 'faible',   '2026-05-28',   6,  3,  350.00, 'Programme de fidélité PME'),
(3,  0.0650, 'faible',   '2026-05-28',   1,  3,  161.33, 'Onboarding avancé + upsell'),
(4,  0.1450, 'faible',   '2026-05-28',   8,  2,   66.75, 'Email de satisfaction post-achat'),
(5,  0.0750, 'faible',   '2026-05-28',   7,  4,  870.00, 'Account manager dédié'),
(6,  0.1100, 'faible',   '2026-05-28',   5,  2,  295.00, 'Offre de renouvellement anticipé'),
(7,  0.0950, 'faible',   '2026-05-28',   3,  3,   65.00, 'Email personnalisé produit'),
(8,  0.0800, 'faible',   '2026-05-28',   2,  3,  220.00, 'Cross-sell sur historique d''achat'),
(9,  0.1300, 'faible',   '2026-05-28',   6,  2,   84.00, 'Email de recommandation produit'),
(10, 0.1050, 'faible',   '2026-05-28',   4,  3,  355.00, 'Relance panier PME'),
-- Inactifs – risque moyen (score 0.32-0.58)
(11, 0.4800, 'moyen',    '2026-05-28',  38,  2,   56.00, 'Campagne email de réactivation'),
(12, 0.4200, 'moyen',    '2026-05-28',  33,  1,  220.00, 'Appel commercial + offre de remise'),
(13, 0.3800, 'moyen',    '2026-05-28',  30,  2,  107.50, 'Newsletter + code promo 10%'),
(14, 0.5500, 'moyen',    '2026-05-28',  43,  1,   58.00, 'Email de réengagement personnalisé'),
(15, 0.4500, 'moyen',    '2026-05-28',  38,  2,  800.00, 'Revue de compte + proposition de valeur'),
(16, 0.3200, 'moyen',    '2026-05-28',  27,  1,  110.00, 'Rappel produits consultés'),
(17, 0.5800, 'moyen',    '2026-05-28',  46,  2,  235.00, 'Relance PME + démonstration produit'),
(18, 0.4100, 'moyen',    '2026-05-28',  33,  1,   40.00, 'Email « Vous nous manquez » + coupon'),
(19, 0.5200, 'moyen',    '2026-05-28',  43,  1,  165.00, 'Webinaire exclusif + essai gratuit'),
(20, 0.3500, 'moyen',    '2026-05-28',  23,  2,   70.00, 'Offre de bienvenue reconquête'),
-- Très inactifs – risque élevé/critique (score 0.68-0.96)
(21, 0.7800, 'eleve',    '2026-05-28', 128,  1,   95.00, 'Offre de réactivation 20% + appel'),
(22, 0.8200, 'eleve',    '2026-05-28', 143,  2,  310.00, 'Campagne win-back PME urgente'),
(23, 0.8900, 'critique', '2026-05-28', 164,  0,    0.00, 'Dernier contact avant archivage'),
(24, 0.7100, 'eleve',    '2026-05-28', 102,  1,  120.00, 'Offre découverte nouveau produit'),
(25, 0.7500, 'eleve',    '2026-05-28', 138,  2,  995.00, 'Réunion stratégique compte grand'),
(26, 0.9400, 'critique', '2026-05-28', 174,  0,    0.00, 'Dernière tentative de réactivation'),
(27, 0.6800, 'eleve',    '2026-05-28',  89,  1,  310.00, 'Remise exceptionnelle 25% PME'),
(28, 0.9600, 'critique', '2026-05-28', 189,  0,    0.00, 'Archivage programmé sauf réponse'),
(29, 0.7600, 'eleve',    '2026-05-28', 123,  1,   65.00, 'Programme retour client spécial'),
(30, 0.7200, 'eleve',    '2026-05-28', 107,  2,  200.00, 'Offre early adopter nouveau produit');
