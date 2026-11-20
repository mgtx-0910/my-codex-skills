---
name: marketingv2-uni-h5-profile
description: marketingV2 的 uni-h5 项目环境切换和 H5 本地构建规则，由 uni-h5-build 主技能读取。
---

# marketingV2 uni-h5 打包规则

这是主技能显式读取的可替换项目规则。优先使用用户明确指定的项目或工作区路径；未指定时，在当前工作区或仓库内定位 `code_V2.0/uni-h5`，若当前目录已是 `code_V2.0` 则定位其下的 `uni-h5`。存在多个无法区分的检出或找不到项目时，先向用户确认；以实际选定的路径、分支与文件内容为准，不要混用不同检出。构建前确认该目录的 `package.json`、`manifest.json`、`common/api.js` 和依赖。交付给主技能的结果包括环境、生效 URL、代码来源和 SHA、临时配置变更、工具、产物目录及验证结果。

## 环境和接口

- 每次打包前必须根据用户指定的目标环境检查对应构建代码中的 `common/api.js`。文件顶部的 `url` 行及注释提供已有环境与地址；在构建工作区将目标环境对应行取消注释，同时注释掉其他已启用的 URL 行，使对象中只有一个生效的接口 `url`。保留其他内容与注释；不要把多个重复属性留在对象里，也不要把开发代理误当作生产 API。
- 以本次选定检出的文件实际内容和注释为准，不把历史 URL 列表写死到技能。不同分支可能有不同的环境及地址，例如某分支才有昌吉配置。环境缺失、含义不清、有多个可能的地址或用户没有指定环境时，先询问；不要自行猜测或使用现有激活地址冒充切换成功。用户明确提供新地址时以其要求为准。
- 优先在隔离构建工作区进行该切换，保留原工作区用户的未提交改动；准确记录源 SHA、是否包含指定的未提交代码及本次 URL 修改，不声称该配置修改属于源提交。如果必须使用原工作区，先核实文件改动，不能覆盖或事后丢弃用户修改。完成后报告生效环境、URL 以及构建时的配置差异。
- 检查 `manifest.json` 中 H5 的 `router.mode`、`router.base`、`domain` 和模板，与目标使用场景核对；`devServer.proxy` 是开发服务器配置，不代表发行后自动具备该代理。发现目标不匹配时说明并按用户要求处理，不擅自改动。

## 构建与检查

- 当前已检查的项目 `package.json` 没有 H5 构建脚本，只有占位测试脚本；不得假设 `npm run build:h5` 可用。`.node-version` 目前写有 `12.16.2`，只是项目历史配置；依赖和实际 HBuilderX 内置运行环境、版本兼容性以本次检查为准，不擅自升级项目依赖或改锁文件。
- 使用命令行生产构建，优先选择项目已验证的构建脚本或独立 uni-app CLI。没有可用脚本时，可检查已安装的 HBuilderX 的 `plugins/uniapp-cli` 编译器和兼容的 Node，直接调用其编译入口，无须启动 HBuilderX 图形界面。HBuilderX 的 `cli publish web` 是另一种方式，可能要求先启动软件或登录；不得将其作为无需软件的独立 CLI。
- 已验证的本机方案：HBuilderX 5.26 自带的 `uniapp-cli/bin/uniapp-cli.js`，使用其 `plugins/node18/node.exe`，在隔离副本中构建成功。路径、版本和运行环境都要按当前机器重新发现，不保证其他版本兼容；确认项目依赖完整且编译器插件可用，不擅自升级依赖或修改锁文件。可参考下面的 PowerShell 命令，将变量替换为本次实际发现的绝对路径；`$project` 指隔离项目副本，`$compiler` 指 `plugins/uniapp-cli`，`$node` 指兼容的 Node 可执行文件，`$output` 应为独立且不存在旧产物的输出目录：

```powershell
$env:UNI_INPUT_DIR = $project
$env:UNI_OUTPUT_DIR = $output
$env:UNI_PLATFORM = 'h5'
$env:NODE_ENV = 'production'
$env:UNI_MINIMIZE = 'true'
$env:VUE_CLI_CONTEXT = $compiler
Push-Location $compiler
try {
    & $node (Join-Path $compiler 'bin/uniapp-cli.js')
    $buildExitCode = $LASTEXITCODE
} finally {
    Pop-Location
}
if ($buildExitCode -ne 0) { throw "H5 构建失败，退出码：$buildExitCode" }
```

- 此方案依赖 HBuilderX 安装目录，但仅启动 Node 编译进程；独立 uni-app CLI 环境可完全不依赖 HBuilderX。以本次实际工具和日志为准，编译退出码之外还要核对完成信息和输出。命令行方式受阻时说明原因，不自行切换图形界面。
- 检查 HBuilderX 的实际输出路径。已观察到的历史产物在 `uni-h5/unpackage/dist/build/web`；其他版本或配置可能输出到其他目录，以构建日志及实际配置为准。该目录被忽略且可能含过期文件和旧 `h5.zip`；不要把旧包、旧文件或历史目录直接当成本次产物，也不要清除用户原有产物。必要时使用隔离工作区构建，核对本次生成的 `index.html` 及其引用资源。
- 重新核对本次构建用的激活 URL；可以检查产物中实际打包的地址及本地启动页面，但压缩、分包或运行时配置可能使文本搜索不足以单独证明正确。区分源码配置检查、产物检查和实际浏览器验证，未执行的检查如实报告。
