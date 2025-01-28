module.exports = {
    semi: true,
    trailingComma: 'es5',
    singleQuote: true,
    printWidth: 100,
    tabWidth: 2,
    useTabs: false,
    bracketSpacing: true,
    bracketSameLine: false,
    arrowParens: 'avoid',
    endOfLine: 'lf',
    importOrder: [
        '^react',
        '^@/(.*)$',
        '^[./]'
    ],
    importOrderSeparation: true,
    importOrderSortSpecifiers: true,
}; 