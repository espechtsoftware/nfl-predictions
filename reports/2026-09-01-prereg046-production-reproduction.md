# PREREG-046 / experiment 076 — independent production reproduction

Date: 2026-09-01  
Scope: read-only production cross-verification of the completed lab cohort; no cloud job, object, registry, or source state was changed.

## Result

**PASS: production independently reproduced the frozen PREREG-046 reader result.** The reader accepted all 54 immutable result shards, all three banks, 216 unique slate-bank groups, and every exact-K80 arm book. It emitted 3,873 bytes / 46 lines of stdout with SHA-256:

`0ef8d6e10fbe8abce37b9971eb386f8d5805f8234d7a890d9ecca2473b38f74d`

The lab did not preserve a byte-addressable first-read transcript, so a literal stdout-byte comparison is unavailable. The values and evidence labels retained in the durable lab ledger commit `4fbb823421419f616ef6f0b4c336a5fba5f8bdd1` match this independent output: all three primaries are unresolved, the factorial interaction is `+0.934 [+0.488, +1.380]`, and `DUAL_EMAX_REF` has the highest mean maximum (`181.078`) and lowest regret (`4.099`). This satisfies the independent-reader requirement in `nfl2/COORDINATION.md` section 5; the missing lab transcript is a provenance limitation, not a numerical disagreement.

## Scientific verdict

Under the frozen PREREG-046 raw realized K80 weekly-maximum estimand:

- Marginal repair alone (`M1D0`) is unresolved at `-0.127`; dependence transplant alone (`M0D1`) is unresolved and leans harmful at `-0.567`; their surgical combination (`M1D1`) is unresolved at `+0.240`.
- The difference-in-differences interaction is positive in every bank (`+1.244`, `+1.506`, `+0.052`) and is `+0.934 [ +0.488, +1.380 ]`. The preregistered branch therefore fires: the value is in a coherent joint law, not independent post-hoc marginal or dependence correction.
- The equal-mass coherent-law reference is best by point estimate. It exceeds every surgical cell, but not every pairwise interval excludes zero; this is not evidence that all pairwise differences are independently confirmed.
- Production should not adopt `M1D0`, `M0D1`, or `M1D1` as a standalone law repair. The actionable route is more coherent joint states—participation/latent role, game state, and event-based DST—and a coherent-law parliament.

The program objective changed after this preregistration to winner-utility. Therefore, this is a valid result for its frozen estimand and a mechanism-routing result, but not by itself a current-objective adoption test. Rescoring these already-open books under winner-utility would be exploratory; prospective settlement remains decisive.

## Frozen identities

| Item | Exact identity |
|---|---|
| Reader archive commit | `066d62d834193c9d1da93cce4e8361cbe97a1f72` |
| Reader archive tree | `18b39463f61f29d6cf83bffd566aa5acb77edbe3` |
| Reader path / SHA-256 | `scripts/prereg046_report.py` / `e39ddce539455d3b61a9bf2dd8e9377a07a2d8689edd30a3464923b7f0b6e92d` |
| Frozen loader SHA-256 | `e6c293e1d83edd11e666bab6b03091a62e9e0100b89e21cff1e59fcb7b60461e` |
| Frozen scorecard SHA-256 | `3fc4fb510c7202c4debe9deb76be3f1457e7b0892ff82d8cb88a995c2dde7d18` |
| Runtime source / runner SHA-256 | `231582afb10720992437f1925518106c1c9f24ed` / `d92efd0ec7535683ed197e9b7d6b073cff993f52faf96ba8ed42417adcc58141` |
| Law-repair maps SHA-256 | `5d6f6029814b4dc453aafaac065d081fa2ef8d3c6e626aa8279635ecc78a2fcd` |
| Image digest | `sha256:a1bbcae3d89b18c4199d118a8b067af8b71382ddff5147435c17d3aa53003006` |
| Benchmark | `v1`, hash `04710846d67fb6c6` |
| Experiment | `076_law_factorial` |

The reader was executed from a clean `git archive` of the reader archive commit with `PYTHONPATH` bound to that archive. Both `nfl2.tasks` and `nfl2.scorecard` resolved inside the isolated archive, not the ambient dirty lab worktree.

## Run and provider identities

| Bank | Frozen run ID | Cloud Run execution / UID | Exact invocation | Provider result |
|---:|---|---|---|---|
| 480 | `076b480r3-20260901T124855Z` | `lab-run-5tgx7` / `f80145f7-5602-46ba-8d9b-24943d98e7cf` | `experiments/076_law_factorial.py --bank=480` | 18/18 succeeded; completed 2026-09-01 13:02:08Z |
| 481 | `076b481r2-20260901T130238Z` | `lab-run-hpfq2` / `768ec5f1-c307-48ac-b1fb-f2457e7aa704` | `experiments/076_law_factorial.py --bank=481` | 18/18 succeeded; completed 2026-09-01 13:15:56Z |
| 482 | `076b482r2-20260901T131625Z` | `lab-run-ccc4z` / `4842c9f0-b841-4f4f-a92d-f86585247710` | `experiments/076_law_factorial.py --bank=482` | 18/18 succeeded; completed 2026-09-01 13:30:35Z |

Every execution description was bound to the runtime source, image digest, run ID, 18 tasks, and exact bank argument shown above. Each shard independently carried the same source, image, benchmark, clean-code identity (`dirty=false`, `diff_sha256=null`), and expected task index.

## Exact object manifest

The cohort contains exactly `result-t00.json` through `result-t17.json` for each run and no additional object. The canonical manifest below uses LF-terminated tab-separated rows in the order shown with columns `URI`, `GENERATION`, `BYTES`, `CRC32C`, `MD5_BASE64`, and `SHA256`. It is 11,556 bytes with SHA-256 `86cc39d5db1ff239028d0035180466c61948e9e13c638ce4943af6865c3e1614`.

```text
URI	GENERATION	BYTES	CRC32C	MD5_BASE64	SHA256
gs://nfl-2-506823-lab/results/076_law_factorial/076b480r3-20260901T124855Z/result-t00.json	1788267719961761	521483	R91QMQ==	S+Cq3Cn729apBxe9DfrZPA==	ff19208dc3328e53324eae81104d6541bc2948bc89c605f844ed9107910dc185
gs://nfl-2-506823-lab/results/076_law_factorial/076b480r3-20260901T124855Z/result-t01.json	1788267695535403	521801	SFY0TA==	kZc171JqZv8trENMsEUt8A==	7b6f7a052b80f53d54342a23e2441a4693b9beb77b07b214ff22f88210958568
gs://nfl-2-506823-lab/results/076_law_factorial/076b480r3-20260901T124855Z/result-t02.json	1788267489301659	522921	cygnRA==	PBhlzXppApBPq8DoA8717w==	af44e5537cc1ef49a4b9a14b2cddada4378964bbe21ea04aec3f1ca0d376d95b
gs://nfl-2-506823-lab/results/076_law_factorial/076b480r3-20260901T124855Z/result-t03.json	1788267701598548	520925	GPNZWg==	h9DUr6y4xazNxl6FveIOog==	20e5ba4b03945171257ed61aaa1681c86edd7221aa76aa82f58f07f6c1f2d55b
gs://nfl-2-506823-lab/results/076_law_factorial/076b480r3-20260901T124855Z/result-t04.json	1788267571308054	521715	yYGscQ==	hlNucEKZMCyQaVCoJJUOYg==	6a571b07849e3c632a3efa7eaac446dd972cc900f42ff05f47b20d80539af166
gs://nfl-2-506823-lab/results/076_law_factorial/076b480r3-20260901T124855Z/result-t05.json	1788267439312509	521499	6CBYdg==	+UrdKBdAaBMVB1sFBAELpA==	cd0e0b1289f9f95391fd4caff84b4bc162d4ca0d07b8ea025958ae4665ffee46
gs://nfl-2-506823-lab/results/076_law_factorial/076b480r3-20260901T124855Z/result-t06.json	1788267664900805	520045	S4BMzA==	Sd/2WWZiG+zY0jP3S9DZqg==	9353e95f6dd3cf4e853f2a711a83e4d01a92b5fc06d452e93e0254c530eaa01e
gs://nfl-2-506823-lab/results/076_law_factorial/076b480r3-20260901T124855Z/result-t07.json	1788267641028293	521787	9lLU9g==	l8DolSKJOG9PVn/A+8p7bg==	2efc859c38100d44385c150998c39da524dcd4db8eb7fae5bd719b8e217775b4
gs://nfl-2-506823-lab/results/076_law_factorial/076b480r3-20260901T124855Z/result-t08.json	1788267585863829	520680	UZQ64A==	FLMylQMJwpLN+TYQGvfiZA==	0a9a6fc5bb1356b9209e27302f1800fa69df2b660c7db0d3417544a4fb573f9c
gs://nfl-2-506823-lab/results/076_law_factorial/076b480r3-20260901T124855Z/result-t09.json	1788267428456138	523121	pjJSwg==	LoRYRrabpkk5nGfDOyvOBA==	87e7af31393ede53b5e6011ecb1e011ba0b92408811bcd912aa621f5e7da0149
gs://nfl-2-506823-lab/results/076_law_factorial/076b480r3-20260901T124855Z/result-t10.json	1788267651642542	522506	9ItiPg==	kqn5VPbruq6lhcPfQ1BMkQ==	0f431b029b3ee627056f1ad34253222e626d72ef350d2a7ba11a8fe416c164fb
gs://nfl-2-506823-lab/results/076_law_factorial/076b480r3-20260901T124855Z/result-t11.json	1788267591432682	521328	4KJy2Q==	RrscEaEb3rrK9gKBqYkcTw==	477fad0d2e82a75920dab3a2c28e4cd5c0e1d1f5fb155a9880710608a648d3ba
gs://nfl-2-506823-lab/results/076_law_factorial/076b480r3-20260901T124855Z/result-t12.json	1788267646488376	522617	ENUeQA==	PLjFoK+y/p9Rw6+0HwlUHA==	4317ed6f0c7c3489270e0015c7b895e81fd517a1c013b1910dc69e32dc5e1545
gs://nfl-2-506823-lab/results/076_law_factorial/076b480r3-20260901T124855Z/result-t13.json	1788267544332837	522272	GBppJQ==	SwIFTAcfgUYoEjf9khoZug==	77c3c79283d778973239a2b8f2812a483139c10c8ffec5210bea2aaed9cfbe6c
gs://nfl-2-506823-lab/results/076_law_factorial/076b480r3-20260901T124855Z/result-t14.json	1788267678097133	522227	RNyyvA==	PI9+PZtMUE/Oc/iw67kXuA==	82e834542950cb40e543f73dc754ee4c6657aac916f85450acfd0b060e6454cd
gs://nfl-2-506823-lab/results/076_law_factorial/076b480r3-20260901T124855Z/result-t15.json	1788267519661336	522744	3zHSeg==	qEkIbbAPP7SsVwhp68LP2w==	12e1dae66e8dbd7844d27efec4c91435024e7f5d3e2b476c10250372b29bf007
gs://nfl-2-506823-lab/results/076_law_factorial/076b480r3-20260901T124855Z/result-t16.json	1788267670738048	522551	xjo8WA==	Q+4D7qAHBltQS76E8DKOFw==	db2d44c1223919312798eee9f026ca4422bc23f2d71b4fd8c244aa2f5dfae3ad
gs://nfl-2-506823-lab/results/076_law_factorial/076b480r3-20260901T124855Z/result-t17.json	1788267708164587	522989	ZwUpHg==	tbiWTuMq+P8PueMck5zOsg==	22bd7fae5762286ba6b425fc1f2bfbf2437c05659029cbd0b85751944f34f2dd
gs://nfl-2-506823-lab/results/076_law_factorial/076b481r2-20260901T130238Z/result-t00.json	1788268552772953	521821	II03nA==	2mHZuTN4O8MQhSry9e+aOQ==	ad9c4aba1f427452e494039e5eb7720400a1845c33929a7c6ec700636d7e42ac
gs://nfl-2-506823-lab/results/076_law_factorial/076b481r2-20260901T130238Z/result-t01.json	1788268480369421	520937	YEesXw==	Q1pDI+PnkP3cgtnxFKNmSw==	7a051f1d7eb1c5d14f4809aba203e67f66350ab4a8efcef09e66e21a439590c4
gs://nfl-2-506823-lab/results/076_law_factorial/076b481r2-20260901T130238Z/result-t02.json	1788268475683544	521224	35l5mw==	3VMkmuW2mh9c3wqSAGOf+w==	e7ed8a7de928f61df3039b22d35fa43aaa04f2f46f7caf00f294198f7ea0275c
gs://nfl-2-506823-lab/results/076_law_factorial/076b481r2-20260901T130238Z/result-t03.json	1788268516863214	521295	Cx/J2Q==	++hFmFyGI6Wuxdxhh7HIUQ==	842f20b8500cc6653d074deab8f9f6579f0b0a094714bb4b19af4e949f77b0ac
gs://nfl-2-506823-lab/results/076_law_factorial/076b481r2-20260901T130238Z/result-t04.json	1788268451072204	521528	AAda0w==	ykZRDOFMM4UxN/R1tw7H3A==	9ce9a25742230e132a37bccf2e133670068c002a7948fac6f6cced1f29700a09
gs://nfl-2-506823-lab/results/076_law_factorial/076b481r2-20260901T130238Z/result-t05.json	1788268457416300	520170	CVefcg==	FcWXwgvKqp9qURVlqKA8Fg==	9508f282769cc7e23f73309caac9adb612cb6ee9db7f7e672cf63bcb50c436c1
gs://nfl-2-506823-lab/results/076_law_factorial/076b481r2-20260901T130238Z/result-t06.json	1788268511561176	521398	eX62ag==	gkEWmfUvT1RBX5aI/ANaTA==	fe213f280e8df3650b5369eddc9aca28d88000635869981a6fa99e7d0a89e3ea
gs://nfl-2-506823-lab/results/076_law_factorial/076b481r2-20260901T130238Z/result-t07.json	1788268440270077	522219	jmuDtQ==	gpnbpviGlEEUEIIPZWZHCg==	0f917a8509a128ecc37be44f4de398d994747ccc1b8c8d95e05168f7f0a6c962
gs://nfl-2-506823-lab/results/076_law_factorial/076b481r2-20260901T130238Z/result-t08.json	1788268480780364	520705	bl3/Ag==	StNwZJl7C6CsXAx/FIiFDg==	92f0beeffa6cc3996315a3ad60dcfbd9d944f5e50f06ea7e1e52091ee141252a
gs://nfl-2-506823-lab/results/076_law_factorial/076b481r2-20260901T130238Z/result-t09.json	1788268332721795	522471	HyTZkA==	NBrx8fZrv4DVGmEnBKT6XQ==	81ad241bac2ecba0f799b90a7c516a0e8049d094f8eed0b444ac8311603233e6
gs://nfl-2-506823-lab/results/076_law_factorial/076b481r2-20260901T130238Z/result-t10.json	1788268350075639	522606	sTV0hw==	9YuIXVO7ENzwUHx5I51rlg==	3f75c757e5643476a558883c474ce596de9b41f744903d5f3b7c6567273de2b3
gs://nfl-2-506823-lab/results/076_law_factorial/076b481r2-20260901T130238Z/result-t11.json	1788268386912222	521830	jSDHFA==	t0j5+ihG1efCYFyFhAto8A==	9cbf66bb8b8ba2e742d62dd359755281a007b28491601b752714b730f622b15c
gs://nfl-2-506823-lab/results/076_law_factorial/076b481r2-20260901T130238Z/result-t12.json	1788268440620924	523422	1s10ig==	HcssGSAFjkd5r2q5zB8l8A==	324a32f250dfd45059d553f4b920852e5b382a40e7e5d5fd438abec2fb17c7b4
gs://nfl-2-506823-lab/results/076_law_factorial/076b481r2-20260901T130238Z/result-t13.json	1788268355993824	523124	S/bePA==	sxteDUExgJ5CT8CgkDTL9w==	44dd76d30e241390fc622a16f98afd770abb51c0f65d48539af3bc6f48d23447
gs://nfl-2-506823-lab/results/076_law_factorial/076b481r2-20260901T130238Z/result-t14.json	1788268330163897	522917	Lc0TlA==	hHaIV5AgffXcXhV0qHdF/w==	e09866b8341fcab1816f6b3398bd965988962816d961e7290cb363ec621ae1db
gs://nfl-2-506823-lab/results/076_law_factorial/076b481r2-20260901T130238Z/result-t15.json	1788268370424719	522305	p8wSNA==	DqlqX5ooIQd+M52uY7IKiQ==	340929b7a0781aad227e2c725fb02ea2d8817822f6449b67367934d055a42313
gs://nfl-2-506823-lab/results/076_law_factorial/076b481r2-20260901T130238Z/result-t16.json	1788268493317150	523131	DzEtxw==	8Ct6NTxY6X4A/ua60qd1IQ==	bc036961ebe101442b2c9afe89c6b95f1cdda52a7aa7d3fc0109ac9bc8df54bc
gs://nfl-2-506823-lab/results/076_law_factorial/076b481r2-20260901T130238Z/result-t17.json	1788268519144550	522187	/c3nsA==	JT2KPF4DmAltxP9TphlNaw==	500fb8a9a0a07b056e568774acea2b34c585663030a5c7673f16c8f0decf5963
gs://nfl-2-506823-lab/results/076_law_factorial/076b482r2-20260901T131625Z/result-t00.json	1788269431269544	522539	YUXhQg==	kWuoN9j5A+cc5sB+gdsBUQ==	233610ec84a11e883e2fae67cadd4b5c4ac19d2d9b434e1c42e91ec1a7c8be6f
gs://nfl-2-506823-lab/results/076_law_factorial/076b482r2-20260901T131625Z/result-t01.json	1788269228014791	521011	XezN5w==	u/5FTfcqNrz8utxcekdUQA==	0edfca5cebadb93ebceb6430f4db0a27d681da8b6d58fe721837e35b24afbcf5
gs://nfl-2-506823-lab/results/076_law_factorial/076b482r2-20260901T131625Z/result-t02.json	1788269134784987	522395	wkUwQw==	Z3kUeq5oyYV7Hn6QRh3QYA==	3f29c6fcd28e02cdc61ef23898cec5cdd18ba2664e50d25a359dab03ddc61a9a
gs://nfl-2-506823-lab/results/076_law_factorial/076b482r2-20260901T131625Z/result-t03.json	1788269290221850	522191	lipG3A==	rR4aP2YoHDPddenv14s+5g==	c271fc14ebbb0496d17dff266b7e19ffbebfb24b879deedf15f9ad698fbe37c8
gs://nfl-2-506823-lab/results/076_law_factorial/076b482r2-20260901T131625Z/result-t04.json	1788269110463330	521613	hhaVzQ==	TDz+stcschIRqEyIfdf/4Q==	01593c746426f2b55bc603bbb0b4b96a94b8f679b68c2b09429219737fde11ef
gs://nfl-2-506823-lab/results/076_law_factorial/076b482r2-20260901T131625Z/result-t05.json	1788269280281748	520316	8tCCkQ==	GO1bN/IUBJ2Yc8nFkUJGGQ==	a643b1fc7304a92b7f3d852a1c449fa5c1eca20f7f93add3e213b1a0c0a2a7f2
gs://nfl-2-506823-lab/results/076_law_factorial/076b482r2-20260901T131625Z/result-t06.json	1788269291794195	521957	Wx23pQ==	uAdA/iFlsH0QDKU+Jqc6jQ==	9fbeeb3118bdb354774c54c992800a4253cf821be782c524ba467a14723eb6de
gs://nfl-2-506823-lab/results/076_law_factorial/076b482r2-20260901T131625Z/result-t07.json	1788269327272323	521318	zBbx+g==	l6Msxy2H6BHkz+NFkFokjw==	bc5392196e2554ae367f1b09a204e74fbc3bf82759314240af77103c594fa814
gs://nfl-2-506823-lab/results/076_law_factorial/076b482r2-20260901T131625Z/result-t08.json	1788269207102440	520325	omdJGg==	UJZm3oA747Ey0kz1QW/hNQ==	ea55ce61b2c9c11989afb0855d6093daa2cadf394fafb92bc98b46d0d3534d11
gs://nfl-2-506823-lab/results/076_law_factorial/076b482r2-20260901T131625Z/result-t09.json	1788269292375055	522856	um4/cQ==	X423ibw3rHLHiPGti4ILzQ==	7840295bdc07270e2d436e9f05d92156ae10fbd4c1f67605f19e0fc3fbedad33
gs://nfl-2-506823-lab/results/076_law_factorial/076b482r2-20260901T131625Z/result-t10.json	1788269295191243	522548	zvuzYQ==	1e8Uwr4kjCtO2JsAHeXYlw==	4bb1b0911595a712d80b5c8c5ee7c11e68e1c8173deac55424a91a1dba33e488
gs://nfl-2-506823-lab/results/076_law_factorial/076b482r2-20260901T131625Z/result-t11.json	1788269175915958	522854	XkC4KA==	x9D0WfgM0Z6IFr+BivyzVg==	c4323f2cd68377f777399aec39704b55b06e41eb0e361d57852394ce454eddfa
gs://nfl-2-506823-lab/results/076_law_factorial/076b482r2-20260901T131625Z/result-t12.json	1788269329233103	522493	jMhuFA==	EyXbn9gK2YYjYb9NbE9MAQ==	be63d48f8f71fbd58a1d9fe896eb2abe7745fc54e8971ecb65da1014ef70973d
gs://nfl-2-506823-lab/results/076_law_factorial/076b482r2-20260901T131625Z/result-t13.json	1788269318247014	522330	jwpMzg==	QYrB9Z7CRuAvlFrAogOMfw==	45a6aaf24c479332efd4e0ea378b9c944cab47633df3b5f4b84c5e0b7b57e9e7
gs://nfl-2-506823-lab/results/076_law_factorial/076b482r2-20260901T131625Z/result-t14.json	1788269296455383	523065	0Xr/cg==	Tiqxoe0gYErayvtuGa5FNQ==	5a4ae5a4b6d0a00bfab04e6a7b8cf88ead228ca9249998bbb1f2a7804967b5a9
gs://nfl-2-506823-lab/results/076_law_factorial/076b482r2-20260901T131625Z/result-t15.json	1788269161759575	522081	C77PPw==	2xR4Pp63qb8pj26aEmntqA==	df9769a413cf8080f13f364620c2cecc84355e1b79ac880d915afb3d5ba5f549
gs://nfl-2-506823-lab/results/076_law_factorial/076b482r2-20260901T131625Z/result-t16.json	1788269324572526	522371	40U+Pw==	ChDFe6v8wmauojkynQzLbA==	a54a856189a20acd5b054a3dc3bb32e235d1e78ac9d9ba36bead8452c29722fd
gs://nfl-2-506823-lab/results/076_law_factorial/076b482r2-20260901T131625Z/result-t17.json	1788269247743032	522452	chqlXQ==	4/M8LFx+8MLVCKbMit+DYA==	c11163d1838415672cf3feb793e4f6d56039daec7a8f9efca09a4a62be648530
```

## Exact independent reader stdout

The following block is the exact 3,873-byte stdout, including its final newline.

```text
PREREG-046 / 076 — fail-closed reader | runs ['076b480r3-20260901T124855Z', '076b481r2-20260901T130238Z', '076b482r2-20260901T131625Z'] | family level 0.9833

PRIMARY K80 M1D0_EMAX    - M0D0_EMAX: -0.127 fam[-0.658, +0.260] banks {480: -0.022, 481: -0.865, 482: 0.506}
             W/L/T 10/7/55 LOSO {2021: -0.135, 2022: 0.111, 2023: -0.27, 2024: -0.214} sign-flip-p 0.7928 VERDICT=UNRESOLVED
PRIMARY K80 M0D1_EMAX    - M0D0_EMAX: -0.567 fam[-1.046, +0.076] banks {480: 0.062, 481: -1.32, 482: -0.444}
             W/L/T 11/21/40 LOSO {2021: -0.41, 2022: -0.407, 2023: -0.615, 2024: -0.838} sign-flip-p 0.0823 VERDICT=UNRESOLVED
PRIMARY K80 M1D1_EMAX    - M0D0_EMAX: +0.240 fam[-0.383, +0.715] banks {480: 1.284, 481: -0.679, 482: 0.114}
             W/L/T 13/12/47 LOSO {2021: 0.2, 2022: 0.529, 2023: 0.181, 2024: 0.048} sign-flip-p 0.5022 VERDICT=UNRESOLVED

NAMED MECHANISM CONTRASTS (PREREG-046):
  M1D1_EMAX - M0D1_EMAX (marginals | dependence): +0.807 [+0.495, +1.190] banks {480: 1.222, 481: 0.641, 482: 0.558}
  M1D1_EMAX - M1D0_EMAX (dependence | marginals): +0.367 [+0.164, +0.570] banks {480: 1.306, 481: 0.187, 482: -0.392}
  M0D0_EMAX - DUAL_EMAX_REF (M0D0_EMAX vs equal-mass reference): -0.433 [-1.020, +0.001] banks {480: -0.606, 481: -0.068, 482: -0.624}
  M1D0_EMAX - DUAL_EMAX_REF (M1D0_EMAX vs equal-mass reference): -0.560 [-1.099, -0.020] banks {480: -0.628, 481: -0.933, 482: -0.118}
  M0D1_EMAX - DUAL_EMAX_REF (M0D1_EMAX vs equal-mass reference): -1.000 [-1.162, -0.853] banks {480: -0.544, 481: -1.388, 482: -1.069}
  M1D1_EMAX - DUAL_EMAX_REF (M1D1_EMAX vs equal-mass reference): -0.193 [-0.653, +0.267] banks {480: 0.678, 481: -0.746, 482: -0.51}
  FACTORIAL INTERACTION (M1D1-M1D0)-(M0D1-M0D0): +0.934 [+0.488, +1.380] banks {480: 1.244, 481: 1.506, 482: 0.052}

SECONDARY PREFIXES (K10/20/30/40; K100 unavailable for exact-K80 books):
  K10: M1D0_EMAX -0.121  M0D1_EMAX +0.555  M1D1_EMAX +1.021
  K20: M1D0_EMAX +0.983  M0D1_EMAX +0.762  M1D1_EMAX +0.721
  K30: M1D0_EMAX +0.189  M0D1_EMAX +0.586  M1D1_EMAX +0.665
  K40: M1D0_EMAX +0.600  M0D1_EMAX +0.276  M1D1_EMAX -0.112
  M0D0_EMAX    weeks >=187 23  >=194 13  >=200 10  >=210 4  >=220 0  >=230 0  >=240 0
  M0D0_EMAX    roster hits >=187 150  >=194 78  >=200 46  >=210 15  >=220 5  >=230 0  >=240 0
  M1D0_EMAX    weeks >=187 25  >=194 13  >=200 11  >=210 4  >=220 0  >=230 0  >=240 0
  M1D0_EMAX    roster hits >=187 149  >=194 81  >=200 48  >=210 15  >=220 5  >=230 0  >=240 0
  M0D1_EMAX    weeks >=187 22  >=194 15  >=200 7  >=210 3  >=220 0  >=230 0  >=240 0
  M0D1_EMAX    roster hits >=187 142  >=194 73  >=200 44  >=210 14  >=220 4  >=230 0  >=240 0
  M1D1_EMAX    weeks >=187 24  >=194 14  >=200 9  >=210 3  >=220 0  >=230 0  >=240 0
  M1D1_EMAX    roster hits >=187 152  >=194 77  >=200 46  >=210 15  >=220 5  >=230 0  >=240 0
  DUAL_EMAX_REF weeks >=187 25  >=194 17  >=200 11  >=210 2  >=220 0  >=230 0  >=240 0
  DUAL_EMAX_REF roster hits >=187 150  >=194 79  >=200 48  >=210 15  >=220 5  >=230 1  >=240 0

PORTFOLIO RELEVANCE (descriptive; never changes the confirmatory verdict):
  M0D0_EMAX    mean/median-max 180.646/180.180 regret 4.531 EITS 49.48 candidate-J 1.000 book-J 1.000 players-added 0.00
  M1D0_EMAX    mean/median-max 180.519/179.643 regret 4.658 EITS 47.70 candidate-J 1.000 book-J 0.859 players-added 2.65
  M0D1_EMAX    mean/median-max 180.078/180.180 regret 5.099 EITS 53.48 candidate-J 1.000 book-J 0.742 players-added 4.31
  M1D1_EMAX    mean/median-max 180.885/180.830 regret 4.291 EITS 51.51 candidate-J 1.000 book-J 0.725 players-added 4.82
  DUAL_EMAX_REF mean/median-max 181.078/180.443 regret 4.099 EITS 54.08 candidate-J 1.000 book-J 0.664 players-added 5.66

ENGAGEMENT: mean K80 turnover vs control per cell:
  turnover_M1D0_EMAX_k80: 0.077
  turnover_M0D1_EMAX_k80: 0.149
  turnover_M1D1_EMAX_k80: 0.160
  turnover_DUAL_EMAX_REF_k80: 0.203
```

