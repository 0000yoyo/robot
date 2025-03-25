'score': item.get('score', 0)
            } for item in semantic_matches
        ]
    })

if __name__ == '__main__':
    # 配置環境變量
    port = int(os.environ.get('PORT', 5000))
    app.run(
        host='0.0.0.0', 
        port=port, 
        debug=os.environ.get('DEBUG', 'False') == 'True'
    )
