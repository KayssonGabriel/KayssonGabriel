# Manutenção do perfil

O README público usa SVGs locais, Markdown e HTML aceito pelo GitHub. O gerador usa Python 3.11 ou superior com a biblioteca padrão. A arte é construída com formas e caminhos vetoriais próprios. As fontes são locais ao dispositivo de quem lê.

## Estrutura

| Caminho | Função |
| --- | --- |
| [config/profile.json](../config/profile.json) | Identidade, textos curtos e seleção de projetos |
| [config/theme.json](../config/theme.json) | Paletas clara e escura |
| [profile_readme/readme.md.in](../profile_readme/readme.md.in) | Apresentação, ordem das seções e posições dos cartões |
| [profile_readme/](../profile_readme/) | Cliente REST, agregação, validação, templates SVG e geração |
| [data/public.json](../data/public.json) | Último conjunto válido de contagens públicas agregadas |
| [data/calendar.json](../data/calendar.json) | Datas, contagens diárias e intensidades do calendário visível sem login |
| [assets/](../assets/) | SVGs usados pelo README |
| [tests/](../tests/) e [workflows](../.github/workflows/) | Testes e automação |

## Como as métricas são calculadas

- **Calendário de contribuições.** O cartão reproduz as contagens e os níveis diários que a página pública do perfil mostra a visitantes sem login. Cada coluna representa uma semana, com os dias de domingo a sábado. O total segue o período apresentado pelo GitHub e pode incluir contagens anônimas que o perfil já optou por tornar visíveis. A coleta não usa credenciais nem obtém detalhes de repositórios privados. [Critérios de contagem do GitHub](https://docs.github.com/en/account-and-profile/reference/profile-contributions-reference)
- **Repositórios.** A API REST lista os repositórios públicos da conta por propriedade. Próprios e forks são contados separadamente. O repositório do perfil fica fora, para as atualizações automáticas não inflarem a atividade.
- **Linguagens.** Cada repositório próprio com linguagem detectada pelo GitHub contribui uma vez, usando o campo de linguagem principal. O SVG mostra as cinco mais frequentes e soma as demais. A tabela textual inclui todas. A quantidade mede a presença da linguagem nos projetos.
- **Commits públicos.** A busca REST aplica a autoria do login identificado para este perfil, a visibilidade pública e a data de autoria. A janela abrange 12 meses-calendário e inclui o mês atual em andamento. Cada par repositório e SHA conta uma vez. O mês vem da data de autoria no fuso registrado no commit. A tabela diferencia projetos próprios, forks da conta e repositórios de terceiros.
- **Cobertura.** O índice do GitHub cobre apenas branches padrão e pode ter atraso. O recorte deixa de fora PRs, issues, revisões, coautoria sem correspondência no campo de autor e calendário privado. Veja as regras na [documentação da busca de commits](https://docs.github.com/en/search-github/searching-on-github/searching-commits).

Os arquivos agregados registram o login, os períodos e as contagens. Mensagens, e-mails, tokens, SHAs individuais e nomes de autores ou repositórios de terceiros ficam fora dos arquivos. A coleta normalmente usa duas requisições REST e uma leitura do calendário público. Os snapshots versionados integram o histórico do repositório.

## Edição e execução local

Edite a apresentação no template e os textos dos destaques em config/profile.json. Depois de trocar uma cor em config/theme.json, confira a legibilidade nos dois temas. Para alterar a geometria, as fontes do sistema ou as animações, edite profile_readme/cards.py. Para remover ou renomear um destaque, remova também o par de SVGs antigo de assets/ depois de gerar o novo conjunto.

Execute na raiz:

~~~sh
python -m unittest discover -s tests -v
python -m profile_readme
python -m profile_readme --check
python -m profile_readme --refresh
python -m profile_readme --static --output preview/static
~~~

O comando sem opções recria os artefatos a partir do JSON local. A opção de atualização consulta dados reais. O modo estático gera outro conjunto para inspeção, com o mesmo conteúdo essencial. Uma faixa de cor passa pelo nome no cabeçalho quando o navegador permite animações. Os cartões têm texto alternativo e cada gráfico tem uma tabela em texto logo abaixo.

## GitHub Actions

A validação roda em pushes e pull requests com acesso de leitura. A atualização roda manualmente e todos os dias às 09h23 UTC (06h23 em São Paulo, UTC−3) na branch padrão. O agendamento pode sofrer atraso e o GitHub pode desativá-lo após 60 dias sem atividade em repositórios públicos. A opção manual fica na aba Actions depois da publicação do workflow.

A atualização usa o token efêmero do próprio repositório. A permissão de escrita fica no job que publica. O checkout usa uma revisão imutável e só mantém autenticação no job que precisa fazer push. A concorrência é serializada. Se alguém publicar na branch entre o início da coleta e o push, a proteção normal do Git recusa o push e a próxima execução refaz a coleta a partir da branch atual. Não há push forçado. A atualização dispara apenas por agendamento e execução manual.

A coleta, a validação dos dados e a renderização terminam antes da escrita. Os arquivos são substituídos individualmente por renomeação e publicados juntos num único commit. Falhas interrompem o workflow antes de publicar. O JSON e os SVGs versionados preservam os últimos resultados válidos e permitem gerar o perfil offline. O GitHub pode manter imagens em cache por algum tempo. O commit só ocorre quando o conteúdo muda.

## Solução de problemas

- **Limite da API ou busca incompleta.** Aguarde a janela de limite e execute novamente. Se a busca atingir 1.000 itens e for truncada, divida o intervalo na implementação antes de publicar números novos.
- **Calendário indisponível.** O calendário vem de um fragmento HTML público do GitHub. Se a estrutura ou os rótulos mudarem, revise o parser e os testes. A atualização é interrompida se uma data faltar ou se a soma dos dias divergir do total exibido.
- **Texto ou gráfico antigo.** Compare com o snapshot atual e execute a verificação offline. Se a verificação passar, abra o SVG na branch padrão e confira o commit que o publicou.
- **Push recusado.** Verifique a proteção da branch, a política de workflows e a referência para a qual o job foi disparado. Execute a atualização novamente a partir da branch padrão depois de resolver o conflito.
- **Atualização de dependências.** A biblioteca padrão acompanha o Python oferecido pelo runner. Para atualizar o checkout, revise o changelog e os avisos de segurança, confirme o SHA de 40 caracteres no repositório oficial e atualize os dois workflows. Rode testes e valide um disparo manual após a revisão.

Referências de implementação no [estudo comparativo](referencias.md) e fontes dos projetos no [levantamento do perfil público](perfil-publico.md).
